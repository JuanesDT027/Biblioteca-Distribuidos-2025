import zmq
import json
import time
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

# ===============================
#   CONFIG ZMQ Y FAILOVER
# ===============================
context = zmq.Context()

# REP: recibe solicitudes del Gestor de Carga
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://0.0.0.0:5557")
rep_socket.setsockopt(zmq.LINGER, 0)

# Configuración de GA primario y réplica
GA_PRIMARIO = "tcp://10.43.102.150:5560"
GA_REPLICA = "tcp://10.43.102.150:5561"
ga_actual = GA_PRIMARIO

print("✅ Actor Préstamo iniciado en 192.168.10.10:5557")
print("📡 Conectado a GA en 10.43.102.150 - Listo para solicitudes...\n")

def conectar_ga():
    """Conecta al GA actual"""
    ga_socket = context.socket(zmq.REQ)
    ga_socket.setsockopt(zmq.LINGER, 0)
    ga_socket.RCVTIMEO = 5000
    ga_socket.SNDTIMEO = 5000
    
    try:
        ga_socket.connect(ga_actual)
        return ga_socket
    except Exception as e:
        print(f"❌ Error conectando a GA en {ga_actual}: {e}")
        return None

def operar_con_ga(operacion, datos):
    """Realiza operación en GA con failover automático"""
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
            print(f"⏰ Timeout - GA {ga_actual} no respondió")
            
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
            return {"status": "error", "msg": "Timeout en GA"}
                
    except Exception as e:
        return {"status": "error", "msg": f"Error de comunicación: {str(e)}"}
    finally:
        if ga_socket:
            ga_socket.close()

# ===============================
#   LOOP PRINCIPAL
# ===============================
while True:
    try:
        print("\n" + "="*60)
        print("⏳ Esperando solicitud de préstamo...")
        mensaje = rep_socket.recv_json()
        print(f"🎯 Solicitud recibida: {mensaje}")

        operacion = mensaje.get("operacion")
        codigo = mensaje.get("codigo")

        if operacion != "prestamo":
            rep_socket.send_json({"status": "error", "msg": f"Operación inválida: {operacion}"})
            continue

        if codigo is None:
            rep_socket.send_json({"status": "error", "msg": "Mensaje inválido: falta 'codigo'"})
            continue

        print(f"📚 Procesando préstamo para código: {codigo}")

        # PASO 1: Leer libro en GA
        print(f"➡ Solicitando libro '{codigo}' al GA...")
        respuesta = operar_con_ga("leer", {"codigo": codigo})
        
        if respuesta["status"] != "ok":
            print(f"❌ Error en lectura GA: {respuesta}")
            rep_socket.send_json(respuesta)
            continue

        libro = LibroUsuario(**respuesta["libro"])
        print(f"✅ Libro obtenido: {libro.titulo} - Ejemplares: {libro.ejemplares_disponibles}")

        # PASO 2: Validar disponibilidad
        if libro.ejemplares_disponibles <= 0:
            msg = f"❌ Sin ejemplares disponibles de '{libro.titulo}'"
            print(msg)
            rep_socket.send_json({"status": "error", "msg": msg})
            continue

        # PASO 3: Actualizar libro
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

        print(f"📝 Actualizando libro en GA...")
        resp_actualizar = operar_con_ga("actualizar", actualizar_msg)

        if resp_actualizar["status"] == "ok":
            msg = f"Préstamo OK: '{libro.titulo}' hasta {fecha_entrega}"
            if ga_actual == GA_REPLICA:
                msg += " [Actualizado en RÉPLICA SECUNDARIA]"
            print(f"✅ {msg}")
            rep_socket.send_json({"status": "ok", "msg": msg})
        else:
            print(f"❌ Error en actualización: {resp_actualizar}")
            rep_socket.send_json(resp_actualizar)

    except Exception as e:
        print(f"💥 Error inesperado: {e}")
        rep_socket.send_json({"status": "error", "msg": str(e)})