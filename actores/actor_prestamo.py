import zmq
import json
import time
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

# ===============================
#   CONFIG ZMQ Y FAILOVER
# ===============================
context = zmq.Context()

# REP: recibe solicitudes del Gestor de Carga (en máquina virtual)
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://*:5557")  # Actor préstamo escucha en PC local
rep_socket.setsockopt(zmq.LINGER, 0)

# Configuración de GA primario y réplica (ambos en máquina virtual 10.43.102.150)
GA_PRIMARIO = "tcp://10.43.102.150:5560"
GA_REPLICA = "tcp://10.43.102.150:5561"
ga_actual = GA_PRIMARIO

def conectar_ga():
    """Conecta al GA actual con failover automático"""
    global ga_actual
    
    ga_socket = context.socket(zmq.REQ)
    ga_socket.setsockopt(zmq.LINGER, 0)
    ga_socket.RCVTIMEO = 3000
    ga_socket.SNDTIMEO = 3000
    
    try:
        ga_socket.connect(ga_actual)
        return ga_socket
    except Exception as e:
        print(f"❌ Error conectando a GA en {ga_actual}: {e}")
        return None

def operacion_ga(operacion, datos):
    """Realiza operación en GA con failover"""
    global ga_actual
    
    ga_socket = conectar_ga()
    if not ga_socket:
        return {"status": "error", "msg": "No se pudo conectar al GA"}
    
    try:
        datos["operacion"] = operacion
        ga_socket.send_json(datos)
        
        try:
            respuesta = ga_socket.recv_json()
            return respuesta
            
        except zmq.Again:
            print(f"⏰ Timeout en GA {ga_actual}, intentando failover...")
            
            # Failover automático
            if ga_actual == GA_PRIMARIO:
                print("🔄 REALIZANDO FALLOVER A RÉPLICA SECUNDARIA...")
                ga_actual = GA_REPLICA
                ga_socket.close()
                
                # Reintentar con réplica
                ga_socket = conectar_ga()
                if ga_socket:
                    ga_socket.send_json(datos)
                    try:
                        respuesta = ga_socket.recv_json()
                        return respuesta
                    except zmq.Again:
                        return {"status": "error", "msg": "Timeout en réplica también"}
            else:
                return {"status": "error", "msg": "Timeout en réplica secundaria"}
                
    except Exception as e:
        return {"status": "error", "msg": f"Error de comunicación: {str(e)}"}
    finally:
        if ga_socket:
            ga_socket.close()

print("✅ Actor Préstamo iniciado en 192.168.10.10:5557")
print("📡 Conectado a GA en 10.43.102.150 - Listo para solicitudes...\n")

# ===============================
#   LOOP PRINCIPAL
# ===============================
while True:
    try:
        print("⏳ Esperando solicitud de préstamo desde Gestor de Carga...")
        mensaje = rep_socket.recv_json()
        print(f"🔎 Actor Préstamo recibió: {mensaje}")

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
        #   PASO 1: Leer libro en GA (con failover)
        # ===============================
        print(f"➡ Solicitando libro al GA en {ga_actual}...")
        respuesta = operacion_ga("leer", {"codigo": codigo})
        
        if respuesta["status"] != "ok":
            print(f"⚠ Error GA: {respuesta}")
            
            # Agregar información de réplica al mensaje de error
            error_msg = respuesta.get("msg", "Error desconocido")
            if ga_actual == GA_REPLICA:
                error_msg += " [Intentado en RÉPLICA SECUNDARIA]"
                
            rep_socket.send_json({"status": "error", "msg": error_msg})
            continue

        libro = LibroUsuario(**respuesta["libro"])
        print(f"✅ Libro obtenido: {libro.titulo}")

        # ===============================
        #   PASO 2: Validar disponibilidad
        # ===============================
        if libro.ejemplares_disponibles <= 0:
            msg = f"❌ Sin ejemplares disponibles de '{libro.titulo}'"
            if ga_actual == GA_REPLICA:
                msg += " [Consultado en RÉPLICA SECUNDARIA]"
            print(msg)
            rep_socket.send_json({"status": "error", "msg": msg})
            continue

        # ===============================
        #   PASO 3: Actualizar libro (con failover)
        # ===============================
        libro.ejemplares_disponibles -= 1
        libro.prestado = True
        fecha_entrega = (datetime.now() + timedelta(weeks=2)).strftime("%Y-%m-%d")

        actualizar_msg = {
            "codigo": codigo,
            "data": {
                "ejemplares_disponibles": libro.ejemplares_disponibles,
                "prestado": True,
                "fecha_entrega": fecha_entrega
            }
        }

        print(f"➡ Actualizando libro en GA...")
        resp_actualizar = operacion_ga("actualizar", actualizar_msg)

        if resp_actualizar["status"] == "ok":
            msg = f"Préstamo OK: '{libro.titulo}' hasta {fecha_entrega}"
            if ga_actual == GA_REPLICA:
                msg += " [Actualizado en RÉPLICA SECUNDARIA - FAILOVER EXITOSO]"
            print(f"✅ {msg}")
            rep_socket.send_json({"status": "ok", "msg": msg})
        else:
            error_msg = resp_actualizar.get("msg", "Error al actualizar")
            if ga_actual == GA_REPLICA:
                error_msg += " [Intentado en RÉPLICA SECUNDARIA]"
            print(f"⚠ GA devolvió error al actualizar: {error_msg}")
            rep_socket.send_json({"status": "error", "msg": error_msg})

    except Exception as e:
        print(f"💥 Error inesperado en actor préstamo: {e}")
        error_msg = str(e)
        if ga_actual == GA_REPLICA:
            error_msg += " [En RÉPLICA SECUNDARIA]"
        rep_socket.send_json({"status": "error", "msg": error_msg})