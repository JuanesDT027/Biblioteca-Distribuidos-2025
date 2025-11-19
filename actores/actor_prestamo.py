import zmq
import json
import time
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

# ===============================
#   CONFIG ZMQ
# ===============================
context = zmq.Context()

# REP: recibe solicitudes del Gestor de Carga
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://*:5557")
rep_socket.setsockopt(zmq.LINGER, 0)

# REQ: conexión con Gestor de Almacenamiento PRINCIPAL
ga_socket_principal = context.socket(zmq.REQ)
ga_socket_principal.setsockopt(zmq.LINGER, 0)
ga_socket_principal.RCVTIMEO = 3000
ga_socket_principal.SNDTIMEO = 3000
ga_socket_principal.connect("tcp://10.43.102.150:5560")

# REQ: conexión con Gestor de Almacenamiento RÉPLICA
ga_socket_replica = context.socket(zmq.REQ)
ga_socket_replica.setsockopt(zmq.LINGER, 0)
ga_socket_replica.RCVTIMEO = 3000
ga_socket_replica.SNDTIMEO = 3000
ga_socket_replica.connect("tcp://10.43.102.150:5561")

USANDO_REPLICA = False
print("✅ Actor Préstamo iniciado - Conectado a GA Principal y Réplica...\n")

def enviar_a_ga(mensaje):
    """Envía mensaje al GA activo (principal o réplica) con failover automático"""
    global USANDO_REPLICA
    
    # Primero intentar con principal
    if not USANDO_REPLICA:
        try:
            ga_socket_principal.send_json(mensaje)
            respuesta = ga_socket_principal.recv_json()
            return respuesta
        except zmq.Again:
            print("⚠️ GA Principal no responde - Cambiando a réplica...")
            USANDO_REPLICA = True
            print("🔄 FAILOVER: Usando Réplica Secundaria")
    
    # Usar réplica si principal falla
    try:
        ga_socket_replica.send_json(mensaje)
        respuesta = ga_socket_replica.recv_json()
        # Verificar si el principal se recuperó
        if not USANDO_REPLICA:
            try:
                ga_socket_principal.send_json({"operacion": "ping"})
                ga_socket_principal.recv_json()
                USANDO_REPLICA = False
                print("🔙 Reconectado a GA Principal")
            except:
                pass
        return respuesta
    except zmq.Again:
        raise Exception("Ambos GA no responden")

# ===============================
#   LOOP PRINCIPAL
# ===============================
while True:
    try:
        print("⏳ Esperando solicitud de préstamo...")
        mensaje = rep_socket.recv_json()
        print(f"🔎 Actor Préstamo recibió: {mensaje}")

        # Validación del formato del mensaje
        if not isinstance(mensaje, dict):
            rep_socket.send_json({"status": "error", "msg": "Mensaje no es JSON válido"})
            continue

        operacion = mensaje.get("operacion")
        codigo = mensaje.get("codigo")

        if operacion != "prestamo":
            rep_socket.send_json({"status": "error", "msg": f"Operación inválida: {operacion}"})
            continue

        if codigo is None:
            rep_socket.send_json({"status": "error", "msg": "Mensaje inválido: falta 'codigo'"})
            continue

        print(f"📚 Procesando préstamo para código: {codigo}")

        # ===============================
        #   PASO 1: Leer libro en GA
        # ===============================
        leer_msg = {"operacion": "leer", "codigo": codigo}
        print(f"➡ Enviando a GA (leer): {leer_msg}")
        
        try:
            respuesta = enviar_a_ga(leer_msg)
            print(f"⬅ Respuesta GA (leer): {respuesta}")
        except Exception as e:
            print(f"❌ Error comunicando con GA: {e}")
            rep_socket.send_json({"status": "error", "msg": "Error de conexión con GA"})
            continue

        if respuesta["status"] != "ok":
            print(f"⚠ Error GA: {respuesta}")
            rep_socket.send_json(respuesta)
            continue

        libro = LibroUsuario(**respuesta["libro"])

        # ===============================
        #   PASO 2: Validar disponibilidad
        # ===============================
        if libro.ejemplares_disponibles <= 0:
            msg = f"❌ Sin ejemplares disponibles de '{libro.titulo}'"
            print(msg)
            rep_socket.send_json({"status": "error", "msg": msg})
            continue

        # ===============================
        #   PASO 3: Actualizar libro
        # ===============================
        libro.ejemplares_disponibles -= 1
        libro.prestado = True
        fecha_entrega = (datetime.now() + timedelta(weeks=2)).strftime("%Y-%m-%d")

        actualizar_msg = {
            "operacion": "actualizar",
            "codigo": codigo,
            "data": {
                "ejemplares_disponibles": libro.ejemplares_disponibles,
                "prestado": True,
                "fecha_entrega": fecha_entrega
            }
        }

        print(f"➡ Enviando a GA (actualizar): {actualizar_msg}")
        
        try:
            resp_actualizar = enviar_a_ga(actualizar_msg)
            print(f"⬅ Respuesta GA (actualizar): {resp_actualizar}")
        except Exception as e:
            print(f"❌ Error actualizando en GA: {e}")
            rep_socket.send_json({"status": "error", "msg": "Error actualizando GA"})
            continue

        if resp_actualizar["status"] == "ok":
            fuente = "RÉPLICA" if USANDO_REPLICA else "PRINCIPAL"
            msg = f"Préstamo OK ({fuente}): '{libro.titulo}' hasta {fecha_entrega}"
            print(f"✅ {msg}")
            rep_socket.send_json({"status": "ok", "msg": msg})
        else:
            print(f"⚠ GA devolvió error al actualizar: {resp_actualizar}")
            rep_socket.send_json(resp_actualizar)

    except Exception as e:
        print(f"💥 Error inesperado en actor préstamo: {e}")
        rep_socket.send_json({"status": "error", "msg": str(e)})