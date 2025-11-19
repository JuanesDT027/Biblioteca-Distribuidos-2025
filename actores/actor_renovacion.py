import zmq
import json
import time
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

context = zmq.Context()

# Socket SUB
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://10.43.102.150:5556")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Renovacion")

# Configuración de GA con failover
GA_PRIMARIO = "tcp://10.43.102.150:5560"
GA_REPLICA = "tcp://10.43.102.150:5561"

ga_actual = GA_PRIMARIO
USANDO_REPLICA = False

def conectar_ga():
    global ga_socket, USANDO_REPLICA
    ga_socket = context.socket(zmq.REQ)
    ga_socket.RCVTIMEO = 3000
    ga_socket.connect(ga_actual)
    
    if USANDO_REPLICA:
        print(f"🔄 Actor Renovación conectado a RÉPLICA SECUNDARIA")
    else:
        print(f"✅ Actor Renovación conectado al GA PRIMARIO")

def intentar_failover():
    global ga_actual, USANDO_REPLICA
    if not USANDO_REPLICA:
        print("🚨 FALLO DETECTADO - Cambiando a réplica secundaria...")
        ga_actual = GA_REPLICA
        USANDO_REPLICA = True
        conectar_ga()
        print("📍 Renovaciones ahora en SEDE SECUNDARIA")
        return True
    return False

# Conexión inicial
conectar_ga()

contador_renovaciones = {}

while True:
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)
    data = json.loads(contenido)
    libro_data = data.get("libro")

    if topico == "Renovacion" and libro_data:
        codigo = libro_data["codigo"]
        ubicacion = "RÉPLICA" if USANDO_REPLICA else "PRINCIPAL"
        print(f"\n📙 Solicitud de renovación recibida → {codigo} [{ubicacion}]")

        # Leer datos del libro con reintentos
        for intento in range(2):
            try:
                ga_socket.send_json({"operacion": "leer", "codigo": codigo})
                respuesta = ga_socket.recv_json()
                break
            except zmq.Again:
                print(f"⚠️ GA no respondió (lectura - intento {intento + 1}).")
                if intento == 0 and intentar_failover():
                    continue
                else:
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
        ubicacion = "RÉPLICA" if USANDO_REPLICA else "PRINCIPAL"
        print(f"✏️ Actualizando fecha_entrega → {nueva_fecha_fmt} en GA [{ubicacion}]...")
        
        try:
            ga_socket.send_json({
                "operacion": "actualizar",
                "codigo": codigo,
                "data": {"fecha_entrega": nueva_fecha_fmt}
            })

            resp = ga_socket.recv_json()
            if resp["status"] == "ok":
                contador_renovaciones[codigo] = renovaciones_previas + 1
                ubicacion = "RÉPLICA" if USANDO_REPLICA else "PRINCIPAL"
                print(f"✅ '{libro.titulo}' renovado hasta {nueva_fecha_fmt} "
                      f"(renovaciones: {contador_renovaciones[codigo]}/2) [{ubicacion}].")
            else:
                print(f"⚠️ Error al actualizar: {resp['msg']}")
        except zmq.Again:
            print("⚠️ GA no respondió (actualización).")