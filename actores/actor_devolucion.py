import zmq
import json
import time
from common.LibroUsuario import LibroUsuario

context = zmq.Context()

# Socket SUB
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://10.43.102.150:5556")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Devolucion")

# Configuración de GA con failover
GA_PRIMARIO = "tcp://10.43.102.150:5560"
GA_REPLICA = "tcp://10.43.102.150:5561"

ga_actual = GA_PRIMARIO
USANDO_REPLICA = False

def conectar_ga():
    global ga_socket, USANDO_REPLICA
    ga_socket = context.socket(zmq.REQ)
    ga_socket.RCVTIMEO = 3000
    ga_socket.connect(ga_actual)
    
    if USANDO_REPLICA:
        print(f"🔄 Actor Devolución conectado a RÉPLICA SECUNDARIA")
    else:
        print(f"✅ Actor Devolución conectado al GA PRIMARIO")

def intentar_failover():
    global ga_actual, USANDO_REPLICA
    if not USANDO_REPLICA:
        print("🚨 FALLO DETECTADO - Cambiando a réplica secundaria...")
        ga_actual = GA_REPLICA
        USANDO_REPLICA = True
        conectar_ga()
        print("📍 Devoluciones ahora en SEDE SECUNDARIA")
        return True
    return False

# Conexión inicial
conectar_ga()

while True:
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)
    libro_data = json.loads(contenido)

    if topico == "Devolucion":
        codigo = libro_data.get("codigo")
        print(f"\n📗 Devolución recibida → {codigo}")

        # Leer datos del GA con reintentos
        for intento in range(2):
            try:
                ga_socket.send_json({"operacion": "leer", "codigo": codigo})
                respuesta = ga_socket.recv_json()
                break
            except zmq.Again:
                print(f"⚠️ GA no respondió (lectura - intento {intento + 1}).")
                if intento == 0 and intentar_failover():
                    continue
                else:
                    continue

        if respuesta["status"] == "ok":
            libro = LibroUsuario(**respuesta["libro"])
            libro.prestado = False
            libro.ejemplares_disponibles += 1
            libro.fecha_entrega = None

            time.sleep(0.2)
            
            try:
                ga_socket.send_json({
                    "operacion": "actualizar",
                    "codigo": codigo,
                    "data": {
                        "prestado": False,
                        "ejemplares_disponibles": libro.ejemplares_disponibles,
                        "fecha_entrega": None
                    }
                })

                resp = ga_socket.recv_json()
                if resp["status"] == "ok":
                    ubicacion = "RÉPLICA" if USANDO_REPLICA else "PRINCIPAL"
                    print(f"✅ Libro '{libro.titulo}' devuelto correctamente [{ubicacion}].")
                else:
                    print(f"⚠️ Error en actualización: {resp['msg']}")
            except zmq.Again:
                print("⚠️ GA no respondió (actualización).")
        else:
            print(f"❌ Libro {codigo} no encontrado en GA.")