import zmq
import json
import time
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

context = zmq.Context()

rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://*:5557")  # Puerto exclusivo para préstamos

ga_socket = context.socket(zmq.REQ)
ga_socket.connect("tcp://localhost:5560")  # GA
ga_socket.RCVTIMEO = 5000  # Timeout

print("✅ Actor Préstamo conectado al Gestor de Almacenamiento (GA)...")

while True:
    try:
        mensaje = rep_socket.recv_json()
        codigo = mensaje.get("codigo")
        print(f"\n📘 Solicitud de préstamo recibida para: {codigo}")

        # Leer libro en GA
        ga_socket.send_json({"operacion": "leer", "codigo": codigo})
        try:
            respuesta = ga_socket.recv_json()
        except zmq.Again:
            rep_socket.send_json({"status": "error", "msg": "Sin respuesta del GA"})
            continue

        if respuesta["status"] == "ok":
            libro = LibroUsuario(**respuesta["libro"])

            if libro.ejemplares_disponibles > 0:
                libro.ejemplares_disponibles -= 1
                libro.prestado = True
                fecha_entrega = (datetime.now() + timedelta(weeks=2)).strftime("%Y-%m-%d")

                # Actualizar GA
                ga_socket.send_json({
                    "operacion": "actualizar",
                    "codigo": codigo,
                    "data": {
                        "ejemplares_disponibles": libro.ejemplares_disponibles,
                        "prestado": True,
                        "fecha_entrega": fecha_entrega
                    }
                })

                try:
                    resp_actualizar = ga_socket.recv_json()
                    if resp_actualizar["status"] == "ok":
                        msg = f"Préstamo OK: '{libro.titulo}' hasta {fecha_entrega}"
                        print(f"✅ {msg}")
                        rep_socket.send_json({"status": "ok", "msg": msg})
                    else:
                        rep_socket.send_json(resp_actualizar)
                except zmq.Again:
                    rep_socket.send_json({"status": "error", "msg": "GA sin respuesta"})
            else:
                msg = f"❌ Sin ejemplares de '{libro.titulo}'"
                print(msg)
                rep_socket.send_json({"status": "error", "msg": msg})
        else:
            rep_socket.send_json(respuesta)

    except Exception as e:
        rep_socket.send_json({"status": "error", "msg": str(e)})