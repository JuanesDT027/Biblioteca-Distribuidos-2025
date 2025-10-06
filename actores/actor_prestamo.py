# actores/actor_prestamo.py
import zmq
import json
import time
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

# Crear contexto de ZMQ
context = zmq.Context()

# Socket REP (recibe solicitudes del Gestor de Carga - GC)
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://*:5557")  # Puerto exclusivo para préstamos

# Socket REQ (comunica con el Gestor de Almacenamiento - GA)
ga_socket = context.socket(zmq.REQ)
ga_socket.connect("tcp://localhost:5560")  # Puerto del GA
ga_socket.RCVTIMEO = 5000  # Timeout de 5 segundos

print("✅ Actor Préstamo iniciado y conectado al Gestor de Almacenamiento (GA)...")

while True:
    try:
        # 1️⃣ Recibir solicitud de préstamo del Gestor de Carga
        mensaje = rep_socket.recv_json()
        codigo = mensaje.get("codigo")
        print(f"\n📥 Solicitud de préstamo recibida para libro {codigo}")

        # 2️⃣ Leer datos del libro desde el GA
        ga_socket.send_json({"operacion": "leer", "codigo": codigo})
        try:
            respuesta = ga_socket.recv_json()
            print("📘 Respuesta del GA (leer):", respuesta)
        except zmq.Again:
            rep_socket.send_json({"status": "error", "msg": "Tiempo de espera al consultar GA"})
            continue

        if respuesta["status"] == "ok":
            libro = LibroUsuario(**respuesta["libro"])

            # 3️⃣ Validar disponibilidad
            if libro.ejemplares_disponibles > 0:
                libro.ejemplares_disponibles -= 1
                libro.prestado = True
                fecha_entrega = (datetime.now() + timedelta(weeks=2)).strftime("%Y-%m-%d")

                print(f"✏️ Actualizando préstamo de '{libro.titulo}' en GA (entrega {fecha_entrega})...")
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
                    print("📤 Respuesta del GA (actualizar):", resp_actualizar)
                    if resp_actualizar["status"] == "ok":
                        msg = f"✅ Préstamo autorizado para '{libro.titulo}' hasta {fecha_entrega}"
                        print(msg)
                        rep_socket.send_json({"status": "ok", "msg": msg})
                    else:
                        rep_socket.send_json({"status": "error", "msg": resp_actualizar["msg"]})
                except zmq.Again:
                    rep_socket.send_json({"status": "error", "msg": "Tiempo de espera al actualizar GA"})
            else:
                msg = f"❌ Préstamo DENEGADO: sin ejemplares disponibles de '{libro.titulo}'"
                print(msg)
                rep_socket.send_json({"status": "error", "msg": msg})
        else:
            msg = f"❌ Libro con código {codigo} no encontrado en GA"
            print(msg)
            rep_socket.send_json({"status": "error", "msg": msg})

    except Exception as e:
        print(f"⚠️ Error en actor préstamo: {e}")
        rep_socket.send_json({"status": "error", "msg": str(e)})