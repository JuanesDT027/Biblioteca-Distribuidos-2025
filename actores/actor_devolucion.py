import zmq
import json
import time
from common.LibroUsuario import LibroUsuario

context = zmq.Context()

# SUB: recibe publicaciones del Gestor de Carga (en máquina virtual)
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://10.43.102.150:5556")  # Conectar a GC en máquina virtual
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Devolucion")

# REQ: conexión con Gestor de Almacenamiento (en máquina virtual)
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

print("✅ Actor Devolución conectado a Gestor de Carga en 10.43.102.150:5556")
print("📡 Listo para recibir publicaciones de devoluciones...")

while True:
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)
    libro_data = json.loads(contenido)

    if topico == "Devolucion":
        codigo = libro_data.get("codigo")
        print(f"\n📗 Devolución recibida → {codigo}")

        # Leer datos del GA
        respuesta = operacion_ga("leer", {"codigo": codigo})
        
        if respuesta["status"] == "ok":
            libro = LibroUsuario(**respuesta["libro"])
            libro.prestado = False
            libro.ejemplares_disponibles += 1
            libro.fecha_entrega = None

            time.sleep(0.2)
            
            # Actualizar en GA
            resp_actualizar = operacion_ga("actualizar", {
                "codigo": codigo,
                "data": {
                    "prestado": False,
                    "ejemplares_disponibles": libro.ejemplares_disponibles,
                    "fecha_entrega": None
                }
            })

            if resp_actualizar["status"] == "ok":
                msg = f"✅ Libro '{libro.titulo}' devuelto correctamente"
                if ga_actual == GA_REPLICA:
                    msg += " [en RÉPLICA SECUNDARIA]"
                print(msg)
            else:
                print(f"⚠️ Error en actualización: {resp_actualizar['msg']}")
        else:
            print(f"❌ Libro {codigo} no encontrado en GA.")