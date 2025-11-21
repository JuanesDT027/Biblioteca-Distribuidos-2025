import zmq
import json
import time
from common.LibroUsuario import LibroUsuario

context = zmq.Context()
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://10.43.102.150:5556")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Devolucion")

# Sockets para GA principal y réplica
ga_socket_principal = context.socket(zmq.REQ)
ga_socket_principal.connect("tcp://10.43.102.150:5560")
ga_socket_principal.RCVTIMEO = 3000

ga_socket_replica = context.socket(zmq.REQ)
ga_socket_replica.connect("tcp://10.43.102.150:5561")
ga_socket_replica.RCVTIMEO = 3000

USANDO_REPLICA = False
print("✅ Actor Devolución conectado a GA Principal y Réplica...")

def enviar_a_ga(mensaje):
    """Envía mensaje al GA activo con failover automático"""
    global USANDO_REPLICA
    
    if not USANDO_REPLICA:
        try:
            ga_socket_principal.send_json(mensaje)
            respuesta = ga_socket_principal.recv_json()
            return respuesta
        except zmq.Again:
            print("⚠️ GA Principal no responde - Cambiando a réplica...")
            USANDO_REPLICA = True
            print("🔄 FAILOVER: Usando Réplica Secundaria")
    
    try:
        ga_socket_replica.send_json(mensaje)
        respuesta = ga_socket_replica.recv_json()
        return respuesta
    except zmq.Again:
        raise Exception("Ambos GA no responden")

while True:
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)
    libro_data = json.loads(contenido)

    if topico == "Devolucion":
        codigo = libro_data.get("codigo")
        fuente = "RÉPLICA" if USANDO_REPLICA else "PRINCIPAL"
        print(f"\n📗 Devolución recibida → {codigo} (GA: {fuente})")

        # Leer datos del GA
        try:
            respuesta = enviar_a_ga({"operacion": "leer", "codigo": codigo})
        except Exception as e:
            print(f"⚠️ Error comunicando con GA: {e}")
            continue

        if respuesta["status"] == "ok":
            libro = LibroUsuario(**respuesta["libro"])
            libro.prestado = False
            libro.ejemplares_disponibles += 1
            libro.fecha_entrega = None

            # Actualizar en GA
            actualizar_msg = {
                "operacion": "actualizar",
                "codigo": codigo,
                "data": {
                    "prestado": False,
                    "ejemplares_disponibles": libro.ejemplares_disponibles,
                    "fecha_entrega": None
                }
            }

            try:
                resp = enviar_a_ga(actualizar_msg)
                if resp["status"] == "ok":
                    fuente = "RÉPLICA" if USANDO_REPLICA else "PRINCIPAL"
                    print(f"✅ Libro '{libro.titulo}' devuelto correctamente (GA: {fuente})")
                else:
                    print(f"⚠️ Error en actualización: {resp['msg']}")
            except Exception as e:
                print(f"⚠️ Error actualizando GA: {e}")
        else:
            print(f"❌ Libro {codigo} no encontrado en GA.")