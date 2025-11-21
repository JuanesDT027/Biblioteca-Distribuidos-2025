import zmq
import json
import time
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

# Crear contexto ZMQ
context = zmq.Context()

# Socket SUB: recibe publicaciones del Gestor de Carga (en máquina virtual)
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://10.43.102.150:5556")  # Conectar a GC en máquina virtual
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Renovacion")

# Configuración de GA primario y réplica (ambos en máquina virtual)
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

print("✅ Actor Renovación conectado a Gestor de Carga en 10.43.102.150:5556")
print("📡 Listo para recibir publicaciones de renovaciones...")

# Estructura para llevar el conteo de renovaciones
contador_renovaciones = {}

while True:
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)
    data = json.loads(contenido)
    libro_data = data.get("libro")

    if topico == "Renovacion" and libro_data:
        codigo = libro_data["codigo"]
        print(f"\n📙 Solicitud de renovación recibida → {codigo}")

        # 1️⃣ Leer datos del libro desde GA
        respuesta = operacion_ga("leer", {"codigo": codigo})
        
        if respuesta["status"] != "ok":
            print(f"❌ Libro {codigo} no encontrado en GA.")
            continue

        libro = LibroUsuario(**respuesta["libro"])

        # Obtener la fecha actual de entrega
        try:
            fecha_actual = datetime.strptime(libro.fecha_entrega, "%Y-%m-%d") if libro.fecha_entrega else datetime.now()
        except Exception:
            fecha_actual = datetime.now()

        # Calcular cantidad de renovaciones previas
        renovaciones_previas = contador_renovaciones.get(codigo, 0)

        if renovaciones_previas >= 2:
            print(f"⛔ Renovación rechazada: '{libro.titulo}' ya fue renovado 2 veces.")
            continue

        # Calcular nueva fecha (+7 días)
        nueva_fecha = fecha_actual + timedelta(days=7)
        nueva_fecha_fmt = nueva_fecha.strftime("%Y-%m-%d")

        # Actualizar en GA
        print(f"✏️ Actualizando fecha_entrega → {nueva_fecha_fmt} en GA...")
        resp_actualizar = operacion_ga("actualizar", {
            "codigo": codigo,
            "data": {"fecha_entrega": nueva_fecha_fmt}
        })

        if resp_actualizar["status"] == "ok":
            contador_renovaciones[codigo] = renovaciones_previas + 1
            msg = f"✅ '{libro.titulo}' renovado hasta {nueva_fecha_fmt} (renovaciones: {contador_renovaciones[codigo]}/2)."
            if ga_actual == GA_REPLICA:
                msg += " [en RÉPLICA SECUNDARIA]"
            print(msg)
        else:
            print(f"⚠️ Error al actualizar: {resp_actualizar['msg']}")