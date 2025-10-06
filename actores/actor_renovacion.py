import zmq
import json
import time
from datetime import datetime
from common.LibroUsuario import LibroUsuario

context = zmq.Context()

sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://localhost:5556")  # GC (PUB)
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Renovacion")

ga_socket = context.socket(zmq.REQ)
ga_socket.connect("tcp://localhost:5560")  # GA
ga_socket.RCVTIMEO = 5000

print("✅ Actor Renovación conectado al Gestor de Almacenamiento (GA)...")

while True:
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)
    data = json.loads(contenido)
    libro_data = data.get("libro")
    fecha_nueva = data.get("fecha_nueva")

    if topico == "Renovacion" and libro_data:
        codigo = libro_data["codigo"]
        print(f"\n📙 Renovación recibida → {codigo}")

        # Leer desde GA
        ga_socket.send_json({"operacion": "leer", "codigo": codigo})
        try:
            respuesta = ga_socket.recv_json()
        except zmq.Again:
            print("⚠️ GA no respondió (lectura).")
            continue

        if respuesta["status"] == "ok":
            libro = LibroUsuario(**respuesta["libro"])

            # Formato de fecha YYYY-MM-DD
            try:
                fecha_fmt = datetime.strptime(fecha_nueva.split(" ")[0], "%Y-%m-%d").strftime("%Y-%m-%d")
            except:
                fecha_fmt = datetime.now().strftime("%Y-%m-%d")

            time.sleep(0.2)
            ga_socket.send_json({
                "operacion": "actualizar",
                "codigo": codigo,
                "data": {"fecha_entrega": fecha_fmt}
            })

            try:
                resp = ga_socket.recv_json()
                if resp["status"] == "ok":
                    print(f"✅ '{libro.titulo}' renovado hasta {fecha_fmt}.")
                else:
                    print(f"⚠️ Error al actualizar: {resp['msg']}")
            except zmq.Again:
                print("⚠️ GA no respondió (actualización).")
        else:
            print(f"❌ Libro {codigo} no encontrado en GA.")