import zmq
import json
import time
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

context = zmq.Context()
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://localhost:5556")  # Puerto del GC (PUB)
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Renovacion")

# Socket REQ: comunica con el Gestor de Almacenamiento (GA)
ga_socket = context.socket(zmq.REQ)
ga_socket.connect("tcp://localhost:5560")  # Puerto del GA
ga_socket.RCVTIMEO = 5000  # Timeout de 5 segundos

ga_socket_replica = context.socket(zmq.REQ)
ga_socket_replica.connect("tcp://10.43.102.150:5561")
ga_socket_replica.RCVTIMEO = 3000

USANDO_REPLICA = False
contador_renovaciones = {}
print("✅ Actor Renovación conectado a GA Principal y Réplica...")

def enviar_a_ga(mensaje):
    """Envía mensaje al GA activo con failover automático"""
    global USANDO_REPLICA
    
    if not USANDO_REPLICA:
        try:
            ga_socket_principal.send_json(mensaje)
            respuesta = ga_socket_principal.recv_json()
            return respuesta
        except zmq.Again:
            print("⚠️ GA Principal no responde - Cambiando a réplica...")
            USANDO_REPLICA = True
            print("🔄 FAILOVER: Usando Réplica Secundaria")
    
    try:
        ga_socket_replica.send_json(mensaje)
        respuesta = ga_socket_replica.recv_json()
        return respuesta
    except zmq.Again:
        raise Exception("Ambos GA no responden")

while True:
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)
    data = json.loads(contenido)
    libro_data = data.get("libro")

    if topico == "Renovacion" and libro_data:
        codigo = libro_data["codigo"]
        fuente = "RÉPLICA" if USANDO_REPLICA else "PRINCIPAL"
        print(f"\n📙 Renovación recibida → {codigo} (GA: {fuente})")

        # Leer datos del libro desde GA
        try:
            respuesta = enviar_a_ga({"operacion": "leer", "codigo": codigo})
        except Exception as e:
            print(f"⚠️ Error comunicando con GA: {e}")
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
        actualizar_msg = {
            "operacion": "actualizar",
            "codigo": codigo,
            "data": {"fecha_entrega": nueva_fecha_fmt}
        }

        try:
            resp = enviar_a_ga(actualizar_msg)
            if resp["status"] == "ok":
                contador_renovaciones[codigo] = renovaciones_previas + 1
                fuente = "RÉPLICA" if USANDO_REPLICA else "PRINCIPAL"
                print(f"✅ '{libro.titulo}' renovado hasta {nueva_fecha_fmt} (GA: {fuente})")
            else:
                print(f"⚠️ Error al actualizar: {resp['msg']}")
        except Exception as e:
            print(f"⚠️ Error actualizando GA: {e}")