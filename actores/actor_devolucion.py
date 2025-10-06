import zmq
import json
import time
from common.LibroUsuario import LibroUsuario

# Crear contexto y sockets
context = zmq.Context()

# Socket SUB (recibe publicaciones del Gestor de Carga - GC)
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://localhost:5556")  # Puerto del GC (PUB)
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Devolucion")

# Socket REQ (comunica con el Gestor de Almacenamiento - GA)
ga_socket = context.socket(zmq.REQ)
ga_socket.connect("tcp://localhost:5560")  # Puerto del GA
ga_socket.RCVTIMEO = 5000  # Timeout de 5 segundos

print("✅ Actor Devolución iniciado y conectado al Gestor de Almacenamiento (GA)...")

while True:
    # Esperar mensaje del GC
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)
    libro_data = json.loads(contenido)

    if topico == "Devolucion":
        codigo = libro_data.get("codigo")

        print(f"\n📥 Mensaje recibido del GC → Devolución de {codigo}")
        print(f"🔎 Solicitando datos del libro {codigo} al GA...")

        # 1️⃣ Leer datos del libro desde GA
        ga_socket.send_json({"operacion": "leer", "codigo": codigo})
        try:
            respuesta = ga_socket.recv_json()
            print("📘 Respuesta del GA (leer):", respuesta)
        except zmq.Again:
            print("⚠️ Tiempo de espera excedido al leer datos del GA.")
            continue

        if respuesta["status"] == "ok":
            libro = LibroUsuario(**respuesta["libro"])

            # Actualizar atributos para devolución
            libro.prestado = False
            libro.ejemplares_disponibles += 1
            libro.fecha_entrega = None

            time.sleep(0.3)  # Pausa breve antes de enviar actualización

            print(f"✏️ Actualizando disponibilidad de '{libro.titulo}' en el GA...")
            ga_socket.send_json({
                "operacion": "actualizar",
                "codigo": codigo,
                "data": {
                    "prestado": False,
                    "ejemplares_disponibles": libro.ejemplares_disponibles,
                    "fecha_entrega": None
                }
            })

            try:
                resp_actualizar = ga_socket.recv_json()
                print("📤 Respuesta del GA (actualizar):", resp_actualizar)
                if resp_actualizar["status"] == "ok":
                    print(f"✅ Libro '{libro.titulo}' devuelto correctamente y actualizado en GA.")
                else:
                    print(f"⚠️ Error al actualizar: {resp_actualizar['msg']}")
            except zmq.Again:
                print("⚠️ Tiempo de espera excedido al comunicar con el GA durante la actualización.")
        else:
            print(f"❌ Libro con código {codigo} no encontrado en el GA.")
