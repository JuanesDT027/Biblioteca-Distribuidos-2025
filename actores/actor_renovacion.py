import zmq
import json
from common.LibroUsuario import LibroUsuario

# Crear contexto ZMQ
context = zmq.Context()

# Socket SUB para recibir mensajes del Gestor de Carga (GC)
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://localhost:5556")  # Puerto del GC (PUB)
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Renovacion")

# Socket REQ para comunicarse con el Gestor de Almacenamiento (GA)
ga_socket = context.socket(zmq.REQ)
ga_socket.connect("tcp://localhost:5560")  # Puerto del GA

print("✅ Actor Renovación iniciado y conectado al Gestor de Almacenamiento (GA)...")

while True:
    # Esperar mensaje de renovación desde el Gestor de Carga
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)

    # Parsear el JSON recibido
    data = json.loads(contenido)
    libro_data = data.get("libro")
    fecha_nueva = data.get("fecha_nueva")

    # Procesar mensaje de renovación
    if topico == "Renovacion" and libro_data:
        codigo = libro_data["codigo"]

        # 1️⃣ Solicitar al GA la información del libro
        ga_socket.send_json({
            "operacion": "leer",
            "codigo": codigo
        })
        respuesta = ga_socket.recv_json()

        if respuesta["status"] == "ok":
            libro = LibroUsuario(**respuesta["libro"])

            # 2️⃣ Actualizar la fecha de entrega en el GA
            ga_socket.send_json({
                "operacion": "actualizar",
                "codigo": codigo,
                "data": {"fecha_entrega": fecha_nueva}
            })
            resp_actualizar = ga_socket.recv_json()

            # 3️⃣ Mostrar resultado
            if resp_actualizar["status"] == "ok":
                print(f"📘 Libro '{libro.titulo}' renovado hasta {fecha_nueva}.")
            else:
                print(f"⚠️ Error actualizando {codigo}: {resp_actualizar['msg']}")
        else:
            print(f"❌ Libro con código {codigo} no encontrado en el Gestor de Almacenamiento.")
