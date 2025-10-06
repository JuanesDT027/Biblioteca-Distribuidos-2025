import zmq
import json
import time
from common.LibroUsuario import LibroUsuario

# ==============================
#  ACTOR DE RENOVACIÓN
#  Comunicación PUB/SUB con GC y REQ/REP con GA
# ==============================

context = zmq.Context()

# Socket SUB -> para recibir mensajes de renovación desde GC
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://localhost:5556")  # Puerto del GC (publicador)
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Renovacion")

# Socket REQ -> para comunicarse con el Gestor de Almacenamiento (GA)
ga_socket = context.socket(zmq.REQ)
ga_socket.connect("tcp://localhost:5560")  # Puerto del GA (almacenamiento)
ga_socket.RCVTIMEO = 5000  # timeout de recepción (5 segundos)
ga_socket.SNDTIMEO = 5000  # timeout de envío (5 segundos)

time.sleep(1)  # Esperar a que la conexión ZMQ se estabilice

print("✅ Actor Renovación iniciado y conectado al Gestor de Almacenamiento (GA)...")

while True:
    try:
        # Esperar mensaje de renovación del GC
        mensaje_raw = sub_socket.recv_string()
        topico, contenido = mensaje_raw.split(" ", 1)
        print(f"\n📨 Mensaje recibido del GC → {topico}")

        # Parsear contenido JSON
        data = json.loads(contenido)
        libro_data = data.get("libro")
        fecha_nueva = data.get("fecha_nueva")

        if topico == "Renovacion" and libro_data:
            codigo = libro_data["codigo"]
            print(f"🔎 Solicitando datos del libro {codigo} al Gestor de Almacenamiento...")

            # 1️⃣ Consultar información actual del libro en GA
            ga_socket.send_json({"operacion": "leer", "codigo": codigo})
            respuesta = ga_socket.recv_json()
            print(f"📥 Respuesta del GA (leer): {respuesta}")

            if respuesta.get("status") == "ok":
                libro = LibroUsuario(**respuesta["libro"])

                # 2️⃣ Actualizar la fecha en el GA
                print(f"✏️ Actualizando fecha_entrega a {fecha_nueva} en el GA...")
                ga_socket.send_json({
                    "operacion": "actualizar",
                    "codigo": codigo,
                    "data": {"fecha_entrega": fecha_nueva}
                })
                resp_actualizar = ga_socket.recv_json()
                print(f"📤 Respuesta del GA (actualizar): {resp_actualizar}")

                if resp_actualizar.get("status") == "ok":
                    print(f"✅ Libro '{libro.titulo}' renovado correctamente hasta {fecha_nueva}.")
                else:
                    print(f"⚠️ Error actualizando {codigo}: {resp_actualizar.get('msg')}")

            else:
                print(f"❌ Libro con código {codigo} no encontrado en el Gestor de Almacenamiento.")

    except zmq.error.Again:
        print("⚠️ Tiempo de espera excedido al comunicar con el Gestor de Almacenamiento (GA).")
        continue
    except Exception as e:
        print(f"❌ Error general en actor de renovación: {e}")
        time.sleep(2)
