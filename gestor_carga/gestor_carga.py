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
#     Cambia SOLO esta variable para elegir el tipo
# ======================================================

# MODO_METRICAS = "multihilo"
MODO_METRICAS = "serial"     


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


# ======================================================
#   CONFIGURACIÓN ARCHIVO DE MÉTRICAS (SERIAL o MULTIHILO)
# ======================================================

if MODO_METRICAS == "serial":
    # Crear carpeta Serial si no existe
    os.makedirs("data/Serial", exist_ok=True)

    # SOLO descomenta la prueba que estás haciendo
    NOMBRE_METRICAS = "data/Serial/metricas5Solicitudes_Serial.csv"
    #NOMBRE_METRICAS = "data/Serial/metricas10Solicitudes_Serial.csv"
    #NOMBRE_METRICAS = "data/Serial/metricas20Solicitudes_Serial.csv"

else:  # MULTIHILO (como antes)
    # SOLO descomenta la prueba multihilo correspondiente
    NOMBRE_METRICAS = "data/metricas5Solicitudes_Multihilo.csv"
    #NOMBRE_METRICAS = "data/metricas10Solicitudes_Multihilo.csv"
    #NOMBRE_METRICAS = "data/metricas20Solicitudes_Multihilo.csv"

# Crear archivo CSV
with open(NOMBRE_METRICAS, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp_llegada",
        "timestamp_salida",
        "tiempo_respuesta",
        "operacion",
        "codigo"
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

    # DEVOLUCIÓN
    if operacion == "devolucion" and libro:
        libro.prestado = False
        libro.ejemplares_disponibles += 1

        rep_socket.send_json({"status": "ok", "msg": "Devolución recibida"})
        pub_socket.send_string(f"Devolucion {json.dumps(libro.to_dict())}")

    # RENOVACIÓN
    elif operacion == "renovacion" and libro:
        nueva_fecha = datetime.now() + timedelta(weeks=1)

        rep_socket.send_json({
            "status": "ok",
            "msg": f"Renovación hasta {nueva_fecha}"
        })

        pub_socket.send_string(
            f"Renovacion {json.dumps({'libro': libro.to_dict(), 'fecha_nueva': str(nueva_fecha)})}"
        )

    # PRÉSTAMO
    elif operacion == "prestamo" and libro:
        prestamo_socket = None
        try:
            prestamo_socket = context.socket(zmq.REQ)
            prestamo_socket.setsockopt(zmq.LINGER, 0)
            prestamo_socket.RCVTIMEO = 5000
            prestamo_socket.SNDTIMEO = 5000
            prestamo_socket.connect("tcp://10.195.41.111:5557")

            prestamo_socket.send_json({"operacion": "prestamo", "codigo": codigo})

            try:
                respuesta = prestamo_socket.recv_json()
                rep_socket.send_json(respuesta)
            except zmq.Again:
                rep_socket.send_json({"status": "error", "msg": "Timeout actor préstamo"})

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
            t_inicio,
            t_fin,
            tiempo_respuesta,
            operacion,
            codigo
        ])

    print(f"⏱ Tiempo de respuesta: {tiempo_respuesta:.4f}s")
