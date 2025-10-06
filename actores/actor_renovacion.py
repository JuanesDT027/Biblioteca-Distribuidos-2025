import zmq
import json
import time
from datetime import datetime
from common.LibroUsuario import LibroUsuario

# Crear contexto de ZMQ
context = zmq.Context()

# Socket SUB (recibe publicaciones del Gestor de Carga - GC)
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://localhost:5556")  # Puerto del GC (PUB)
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Renovacion")

# Socket REQ (comunica con el Gestor de Almacenamiento - GA)
ga_socket = context.socket(zmq.REQ)
ga_socket.connect("tcp://localhost:5560")  # Puerto del GA
ga_socket.RCVTIMEO = 5000  # Timeout de 5 segundos

print("✅ Actor Renovación iniciado y conectado al Gestor de Almacenamiento (GA)...")

while True:
    # Esperar mensaje del Gestor de Carga
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)
    data = json.loads(contenido)

    libro_data = data.get("libro")
    fecha_nueva = data.get("fecha_nueva")

    if topico == "Renovacion" and libro_data:
        codigo = libro_data["codigo"]

        print(f"\n📥 Mensaje recibido del GC → Renovacion")
        print(f"🔎 Solicitando datos del libro {codigo} al Gestor de Almacenamiento...")

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

            # 2️⃣ Convertir la fecha a formato estándar YYYY-MM-DD
            try:
                # Si la fecha tiene hora, tomar solo la parte de la fecha
                fecha_dt = datetime.strptime(fecha_nueva.split(" ")[0], "%Y-%m-%d")
                fecha_nueva_fmt = fecha_dt.strftime("%Y-%m-%d")
            except Exception:
                # En caso de error, usar la fecha actual como respaldo
                fecha_nueva_fmt = datetime.now().strftime("%Y-%m-%d")

            # Breve pausa antes del segundo envío para evitar colisiones de socket
            time.sleep(0.3)

            print(f"✏️ Actualizando fecha_entrega a {fecha_nueva_fmt} en el GA...")
            ga_socket.send_json({
                "operacion": "actualizar",
                "codigo": codigo,
                "data": {"fecha_entrega": fecha_nueva_fmt}
            })

            try:
                resp_actualizar = ga_socket.recv_json()
                print("📤 Respuesta del GA (actualizar):", resp_actualizar)
                if resp_actualizar["status"] == "ok":
                    print(f"✅ Libro '{libro.titulo}' renovado correctamente hasta {fecha_nueva_fmt}.")
                else:
                    print(f"⚠️ Error al actualizar: {resp_actualizar['msg']}")
            except zmq.Again:
                print("⚠️ Tiempo de espera excedido al comunicar con el GA durante la actualización.")
        else:
            print(f"❌ Libro con código {codigo} no encontrado en el GA.")