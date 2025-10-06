import zmq
import json
import time
from common.LibroUsuario import LibroUsuario

context = zmq.Context()

sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://localhost:5556")  # GC (PUB)
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Devolucion")

ga_socket = context.socket(zmq.REQ)
ga_socket.connect("tcp://localhost:5560")  # GA
ga_socket.RCVTIMEO = 5000

print("✅ Actor Devolución conectado al Gestor de Almacenamiento (GA)...")

while True:
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)
    libro_data = json.loads(contenido)

    if topico == "Devolucion":
        codigo = libro_data.get("codigo")
        print(f"\n📗 Devolución recibida → {codigo}")

        # Leer datos del GA
        ga_socket.send_json({"operacion": "leer", "codigo": codigo})
        try:
            respuesta = ga_socket.recv_json()
        except zmq.Again:
            print("⚠️ GA no respondió (lectura).")
            continue

        if respuesta["status"] == "ok":
            libro = LibroUsuario(**respuesta["libro"])
            libro.prestado = False
            libro.ejemplares_disponibles += 1
            libro.fecha_entrega = None

            time.sleep(0.2)
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
                resp = ga_socket.recv_json()
                if resp["status"] == "ok":
                    print(f"✅ Libro '{libro.titulo}' devuelto correctamente.")
                else:
                    print(f"⚠️ Error en actualización: {resp['msg']}")
            except zmq.Again:
                print("⚠️ GA no respondió (actualización).")
        else:
            print(f"❌ Libro {codigo} no encontrado en GA.")