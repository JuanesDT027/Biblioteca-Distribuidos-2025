import time
import zmq
import json
import csv
import os
from time import time as now
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

# ======================================================
#                CONFIGURACIÓN DEL MODO
# ======================================================
MODO_METRICAS = "serial"  # o "multihilo"

# ======================================================
#  CONFIGURACIÓN ZMQ
# ======================================================
context = zmq.Context()

# REP → recibe solicitudes de los PS
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://*:5555")
time.sleep(1)

# PUB → envía eventos a actores
pub_socket = context.socket(zmq.PUB)
pub_socket.bind("tcp://*:5556")

# ======================================================
# CONFIGURACIÓN FAILOVER GA
# ======================================================
GA_PRIMARIO = "tcp://localhost:5560"
GA_REPLICA = "tcp://localhost:5561"
ga_actual = GA_PRIMARIO

# IP del actor préstamo en PC local
ACTOR_PRESTAMO_IP = "tcp://192.168.10.10:5557"

# ======================================================
# BASE DE DATOS SIMULADA
# ======================================================
libros = {}

def cargar_libros():
    with open("data/libros.txt", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                libros[data["codigo"]] = LibroUsuario(**data)
            except:
                print("⚠️ Error leyendo línea:", line)

cargar_libros()
print("✅ Gestor de Carga iniciado y listo para recibir solicitudes...")
print(f"📡 Conectando a Actor Préstamo en: {ACTOR_PRESTAMO_IP}")

# ======================================================
#   FUNCIONES DE FAILOVER SIMPLIFICADAS
# ======================================================
def verificar_ga():
    """Verifica si el GA actual está disponible"""
    try:
        ga_socket = context.socket(zmq.REQ)
        ga_socket.setsockopt(zmq.LINGER, 0)
        ga_socket.RCVTIMEO = 2000
        ga_socket.connect(ga_actual)
        
        # Usar operación de listar que es más liviana
        ga_socket.send_json({"operacion": "listar"})
        respuesta = ga_socket.recv_json()
        ga_socket.close()
        
        print(f"✅ GA {ga_actual} está disponible")
        return True
    except:
        print(f"❌ GA {ga_actual} no responde")
        return False

def realizar_failover_si_necesario():
    """Realiza failover automático si es necesario"""
    global ga_actual
    
    if ga_actual == GA_PRIMARIO:
        if not verificar_ga():
            print("🔄 DETECTANDO FALLO DEL GA PRIMARIO - INICIANDO FALLOVER...")
            ga_actual = GA_REPLICA
            print("✅ FAILOVER COMPLETADO - Usando RÉPLICA SECUNDARIA")
            return True
    return False

# ======================================================
#   CONFIGURACIÓN ARCHIVO DE MÉTRICAS
# ======================================================
if MODO_METRICAS == "serial":
    os.makedirs("data/Serial", exist_ok=True)
    NOMBRE_METRICAS = "data/Serial/metricas5Solicitudes_Serial.csv"
else:
    NOMBRE_METRICAS = "data/metricas5Solicitudes_Multihilo.csv"

with open(NOMBRE_METRICAS, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp_llegada", "timestamp_salida", "tiempo_respuesta", 
        "operacion", "codigo", "replica_utilizada"
    ])

print(f"📁 Guardando métricas en: {NOMBRE_METRICAS}")

# ======================================================
#                   BUCLE PRINCIPAL
# ======================================================
while True:
    t_inicio = now()

    mensaje_raw = rep_socket.recv_json()
    operacion = mensaje_raw.get("operacion")
    codigo = mensaje_raw.get("codigo")

    libro = libros.get(codigo)
    print(f"\n📩 Operación recibida: {operacion} → {codigo}")

    # Verificar failover antes de procesar
    replica_utilizada = realizar_failover_si_necesario() or (ga_actual == GA_REPLICA)

    # DEVOLUCIÓN (Asíncrona - Pub/Sub)
    if operacion == "devolucion" and libro:
        libro.prestado = False
        libro.ejemplares_disponibles += 1

        mensaje_respuesta = "Devolución recibida"
        if replica_utilizada:
            mensaje_respuesta += " [Procesado en RÉPLICA SECUNDARIA]"

        rep_socket.send_json({"status": "ok", "msg": mensaje_respuesta})
        pub_socket.send_string(f"Devolucion {json.dumps(libro.to_dict())}")

    # RENOVACIÓN (Asíncrona - Pub/Sub)
    elif operacion == "renovacion" and libro:
        nueva_fecha = datetime.now() + timedelta(weeks=1)

        mensaje_respuesta = f"Renovación hasta {nueva_fecha}"
        if replica_utilizada:
            mensaje_respuesta += " [Procesado en RÉPLICA SECUNDARIA]"

        rep_socket.send_json({"status": "ok", "msg": mensaje_respuesta})
        pub_socket.send_string(
            f"Renovacion {json.dumps({'libro': libro.to_dict(), 'fecha_nueva': str(nueva_fecha)})}"
        )

    # PRÉSTAMO (Síncrona - REQ/REP)
    elif operacion == "prestamo" and libro:
        prestamo_socket = None
        try:
            prestamo_socket = context.socket(zmq.REQ)
            prestamo_socket.setsockopt(zmq.LINGER, 0)
            prestamo_socket.RCVTIMEO = 10000
            prestamo_socket.SNDTIMEO = 5000
            
            prestamo_socket.connect(ACTOR_PRESTAMO_IP)
            print(f"🔗 Conectado a Actor Préstamo en: {ACTOR_PRESTAMO_IP}")

            # Enviar mensaje simple como antes
            mensaje_prestamo = {"operacion": "prestamo", "codigo": codigo}
            prestamo_socket.send_json(mensaje_prestamo)
            print(f"📤 Enviando préstamo a actor: {mensaje_prestamo}")

            try:
                respuesta = prestamo_socket.recv_json()
                print(f"📥 Respuesta del actor préstamo: {respuesta}")
                
                # Agregar info de réplica si es necesario
                if replica_utilizada and respuesta["status"] == "ok":
                    respuesta["msg"] += " [Operación en RÉPLICA SECUNDARIA]"
                
                rep_socket.send_json(respuesta)
            except zmq.Again:
                error_msg = "Timeout actor préstamo - No respondió en 10 segundos"
                rep_socket.send_json({"status": "error", "msg": error_msg})

        except Exception as e:
            rep_socket.send_json({"status": "error", "msg": str(e)})
        finally:
            if prestamo_socket:
                prestamo_socket.close()

    # DISPONIBILIDAD
    elif operacion == "disponibilidad" and libro:
        rep_socket.send_json({
            "status": "ok",
            "ejemplares_disponibles": libro.ejemplares_disponibles,
            "codigo": libro.codigo,
            "titulo": libro.titulo
        })

    # ERROR
    else:
        rep_socket.send_json({
            "status": "error",
            "msg": f"Operación inválida o libro '{codigo}' no existe"
        })

    # REGISTRO MÉTRICAS
    t_fin = now()
    tiempo_respuesta = t_fin - t_inicio

    with open(NOMBRE_METRICAS, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            t_inicio, t_fin, tiempo_respuesta, operacion, codigo,
            "REPLICA" if replica_utilizada else "PRIMARIO"
        ])

    print(f"⏱ Tiempo de respuesta: {tiempo_respuesta:.4f}s")