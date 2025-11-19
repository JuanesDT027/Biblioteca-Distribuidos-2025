import zmq
import json
import time
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

# ===============================
#   CONFIG ZMQ CON FAILOVER
# ===============================
context = zmq.Context()

# REP: recibe solicitudes del Gestor de Carga
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://*:5557")
rep_socket.setsockopt(zmq.LINGER, 0)

# Configuración de GA primario y réplica
GA_PRIMARIO = "tcp://10.43.102.150:5560"
GA_REPLICA = "tcp://10.43.102.150:5561"

ga_actual = GA_PRIMARIO
USANDO_REPLICA = False

def conectar_ga():
    """Conecta al GA actual (primario o réplica)"""
    global ga_socket, USANDO_REPLICA
    ga_socket = context.socket(zmq.REQ)
    ga_socket.setsockopt(zmq.LINGER, 0)
    ga_socket.RCVTIMEO = 3000  # Timeout más corto para failover rápido
    ga_socket.SNDTIMEO = 3000
    ga_socket.connect(ga_actual)
    
    if USANDO_REPLICA:
        print(f"🔄 Conectado a RÉPLICA SECUNDARIA: {ga_actual}")
    else:
        print(f"✅ Conectado a GA PRIMARIO: {ga_actual}")

def intentar_failover():
    """Intenta cambiar a la réplica secundaria"""
    global ga_actual, USANDO_REPLICA
    if not USANDO_REPLICA:
        print("🚨 FALLO DETECTADO - Intentando failover a réplica secundaria...")
        ga_actual = GA_REPLICA
        USANDO_REPLICA = True
        conectar_ga()
        print("📍 Ahora operando desde SEDE SECUNDARIA (RÉPLICA)")
        return True
    return False

def reconectar_primario():
    """Vuelve a conectar al GA primario cuando esté disponible"""
    global ga_actual, USANDO_REPLICA
    if USANDO_REPLICA:
        print("🔄 Verificando disponibilidad del GA primario...")
        ga_actual = GA_PRIMARIO
        USANDO_REPLICA = False
        conectar_ga()
        print("✅ Reconectado al GA PRIMARIO - Sede principal operativa")
        return True
    return False

# Conexión inicial
conectar_ga()
print("✅ Actor Préstamo iniciado con sistema de failover\n")

# ===============================
#   LOOP PRINCIPAL CON FAILOVER
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
        #   PASO 1: Leer libro en GA (con reintentos)
        # ===============================
        for intento in range(2):  # 2 intentos: primario + réplica
            leer_msg = {"operacion": "leer", "codigo": codigo}
            print(f"➡ Enviando a GA (leer) - Intento {intento + 1}: {leer_msg}")
            
            try:
                ga_socket.send_json(leer_msg)
                respuesta = ga_socket.recv_json()
                print(f"⬅ Respuesta GA (leer): {respuesta}")
                break  # Éxito, salir del bucle de reintentos
                
            except zmq.Again:
                print(f"❌ Timeout GA (intento {intento + 1})")
                if intento == 0 and intentar_failover():
                    continue  # Reintentar con réplica
                else:
                    rep_socket.send_json({"status": "error", "msg": "Timeout GA - Sistema no disponible"})
                    break
                    
        else:
            # Si llegamos aquí, ambos intentos fallaron
            rep_socket.send_json({"status": "error", "msg": "Sistema de almacenamiento no disponible"})
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
            ga_socket.send_json(actualizar_msg)
            resp_actualizar = ga_socket.recv_json()
            print(f"⬅ Respuesta GA (actualizar): {resp_actualizar}")
            
        except zmq.Again:
            print("❌ Timeout en actualización")
            # Intentar reconectar al primario si estamos en réplica
            if USANDO_REPLICA:
                reconectar_primario()
            rep_socket.send_json({"status": "error", "msg": "Timeout en actualización"})
            continue

        if resp_actualizar["status"] == "ok":
            msg = f"Préstamo OK: '{libro.titulo}' hasta {fecha_entrega}"
            if USANDO_REPLICA:
                msg += " [OPERADO DESDE RÉPLICA]"
            print(f"✅ {msg}")
            rep_socket.send_json({"status": "ok", "msg": msg})
            
            # Intentar volver al primario después de operación exitosa
            if USANDO_REPLICA:
                time.sleep(1)  # Pequeña pausa antes de verificar primario
                reconectar_primario()
                
        else:
            print(f"⚠ GA devolvió error al actualizar: {resp_actualizar}")
            rep_socket.send_json(resp_actualizar)

    except Exception as e:
        print(f"💥 Error inesperado en actor préstamo: {e}")
        rep_socket.send_json({"status": "error", "msg": str(e)})