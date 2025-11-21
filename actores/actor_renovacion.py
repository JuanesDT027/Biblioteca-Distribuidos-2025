# ======================================
# actores/actor_renovacion.py
# ======================================
import zmq
import json
import time
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

# Crear contexto ZMQ
context = zmq.Context()

# Socket SUB: recibe publicaciones del Gestor de Carga (GC)
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://10.43.102.150:5556")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Renovacion")

# Socket REQ: comunica con el Gestor de Almacenamiento (GA)
ga_socket = context.socket(zmq.REQ)
ga_socket.connect("tcp://10.43.102.150:5560")
ga_socket.RCVTIMEO = 5000  # Timeout de 5 segundos

print("✅ Actor Renovación conectado al Gestor de Almacenamiento (GA)...")

# Estructura para llevar el conteo de renovaciones
contador_renovaciones = {}

while True:
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)
    data = json.loads(contenido)
    libro_data = data.get("libro")

    if topico == "Renovacion" and libro_data:
        codigo = libro_data["codigo"]
        print(f"\n📙 Solicitud de renovación recibida → {codigo}")

        # 1️⃣ Leer datos del libro desde GA
        ga_socket.send_json({"operacion": "leer", "codigo": codigo})
        try:
            respuesta = ga_socket.recv_json()
        except zmq.Again:
            print("⚠️ GA no respondió (lectura).")
            continue

        if respuesta["status"] != "ok":
            print(f"❌ Libro {codigo} no encontrado en GA.")
            continue

        libro = LibroUsuario(**respuesta["libro"])

        # Obtener la fecha actual de entrega
        try:
            fecha_actual = datetime.strptime(libro.fecha_entrega, "%Y-%m-%d") if libro.fecha_entrega else datetime.now()
        except Exception:
            fecha_actual = datetime.now()

        # Calcular cantidad de renovaciones previas
        renovaciones_previas = contador_renovaciones.get(codigo, 0)

        if renovaciones_previas >= 2:
            print(f"⛔ Renovación rechazada: '{libro.titulo}' ya fue renovado 2 veces.")
            continue

        # Calcular nueva fecha (+7 días)
        nueva_fecha = fecha_actual + timedelta(days=7)
        nueva_fecha_fmt = nueva_fecha.strftime("%Y-%m-%d")

        # Actualizar en GA
        print(f"✏️ Actualizando fecha_entrega → {nueva_fecha_fmt} en GA...")
        ga_socket.send_json({
            "operacion": "actualizar",
            "codigo": codigo,
            "data": {"fecha_entrega": nueva_fecha_fmt}
        })

        try:
            resp = ga_socket.recv_json()
            if resp["status"] == "ok":
                contador_renovaciones[codigo] = renovaciones_previas + 1
                print(f"✅ '{libro.titulo}' renovado hasta {nueva_fecha_fmt} "
                      f"(renovaciones: {contador_renovaciones[codigo]}/2).")
            else:
                print(f"⚠️ Error al actualizar: {resp['msg']}")
        except zmq.Again:
            print("⚠️ GA no respondió (actualización).")
