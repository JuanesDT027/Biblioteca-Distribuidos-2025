import zmq
import json
import time
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

# ===============================
#   CONFIG ZMQ
# ===============================
context = zmq.Context()

# REP: recibe solicitudes del Gestor de Carga
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://*:5557")  # Puerto del actor préstamo
rep_socket.setsockopt(zmq.LINGER, 0)

# REQ: conexión con Gestor de Almacenamiento (GA)
ga_socket = context.socket(zmq.REQ)
ga_socket.setsockopt(zmq.LINGER, 0)
ga_socket.RCVTIMEO = 5000
ga_socket.SNDTIMEO = 5000
ga_socket.connect("tcp://10.43.102.150:5560")

print("✅ Actor Préstamo iniciado y conectado al GA...\n")

# ===============================
#   LOOP PRINCIPAL
# ===============================
while True:
    try:
        print("⏳ Esperando solicitud de préstamo...")
        mensaje = rep_socket.recv_json()
        print(f"🔎 Actor Préstamo recibió: {mensaje}")

        # Validación del formato del mensaje
        if not isinstance(mensaje, dict):
            rep_socket.send_json({"status": "error", "msg": "Mensaje no es JSON válido"})
            continue

        operacion = mensaje.get("operacion")
        codigo = mensaje.get("codigo")

        if operacion != "prestamo":
            rep_socket.send_json({"status": "error", "msg": f"Operación inválida: {operacion}"})
            continue

        if codigo is None:
            rep_socket.send_json({"status": "error", "msg": "Mensaje inválido: falta 'codigo'"})
            continue

        print(f"📚 Procesando préstamo para código: {codigo}")

        # ===============================
        #   PASO 1: Leer libro en GA
        # ===============================
        leer_msg = {"operacion": "leer", "codigo": codigo}
        print(f"➡ Enviando a GA (leer): {leer_msg}")
        ga_socket.send_json(leer_msg)

        try:
            respuesta = ga_socket.recv_json()
            print(f"⬅ Respuesta GA (leer): {respuesta}")
        except zmq.Again:
            print("❌ Timeout esperando respuesta del GA (leer)")
            rep_socket.send_json({"status": "error", "msg": "Timeout GA en lectura"})
            continue

        if respuesta["status"] != "ok":
            print(f"⚠ Error GA: {respuesta}")
            rep_socket.send_json(respuesta)
            continue

        libro = LibroUsuario(**respuesta["libro"])

        # ===============================
        #   PASO 2: Validar disponibilidad
        # ===============================
        if libro.ejemplares_disponibles <= 0:
            msg = f"❌ Sin ejemplares disponibles de '{libro.titulo}'"
            print(msg)
            rep_socket.send_json({"status": "error", "msg": msg})
            continue

        # ===============================
        #   PASO 3: Actualizar libro
        # ===============================
        libro.ejemplares_disponibles -= 1
        libro.prestado = True
        fecha_entrega = (datetime.now() + timedelta(weeks=2)).strftime("%Y-%m-%d")

        actualizar_msg = {
            "operacion": "actualizar",
            "codigo": codigo,
            "data": {
                "ejemplares_disponibles": libro.ejemplares_disponibles,
                "prestado": True,
                "fecha_entrega": fecha_entrega
            }
        }

        print(f"➡ Enviando a GA (actualizar): {actualizar_msg}")
        ga_socket.send_json(actualizar_msg)

        try:
            resp_actualizar = ga_socket.recv_json()
            print(f"⬅ Respuesta GA (actualizar): {resp_actualizar}")
        except zmq.Again:
            print("❌ Timeout esperando respuesta del GA (actualizar)")
            rep_socket.send_json({"status": "error", "msg": "Timeout GA en actualización"})
            continue

        if resp_actualizar["status"] == "ok":
            msg = f"Préstamo OK: '{libro.titulo}' hasta {fecha_entrega}"
            print(f"✅ {msg}")
            rep_socket.send_json({"status": "ok", "msg": msg})
        else:
            print(f"⚠ GA devolvió error al actualizar: {resp_actualizar}")
            rep_socket.send_json(resp_actualizar)

    except Exception as e:
        print(f"💥 Error inesperado en actor préstamo: {e}")
        rep_socket.send_json({"status": "error", "msg": str(e)})
