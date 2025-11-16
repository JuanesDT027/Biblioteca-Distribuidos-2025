import time
import zmq
import json
import csv
from time import time as now
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

# ================================
#  CONFIGURACIÓN ZMQ
# ================================

context = zmq.Context()

# REP → recibe solicitudes de los PS
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://*:5555")

time.sleep(1)

# PUB → envía eventos a actores
pub_socket = context.socket(zmq.PUB)
pub_socket.bind("tcp://*:5556")

# ================================
# BASE DE DATOS SIMULADA
# ================================

libros = {}  # diccionario de libros en memoria


# ================================
# CARGAR LIBROS INICIALES
# ================================

def cargar_libros():
    with open("data/libros.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                libros[data["codigo"]] = LibroUsuario(**data)
            except json.JSONDecodeError as e:
                print(f"⚠️ Error leyendo línea: {line}")
                print(e)


cargar_libros()
print("✅ Gestor de Carga iniciado y listo para recibir solicitudes...")


# ================================
# ARCHIVO DE MÉTRICAS
# ================================

with open("metricas_gc.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp_llegada",
        "timestamp_salida",
        "tiempo_respuesta",
        "operacion",
        "codigo"
    ])


# ================================
# BUCLE PRINCIPAL
# ================================

while True:
    # marcar tiempo de llegada
    t_inicio = now()

    mensaje_raw = rep_socket.recv_json()
    operacion = mensaje_raw.get("operacion")
    codigo = mensaje_raw.get("codigo")

    libro = libros.get(codigo)
    print(f"\n📩 Operación recibida: {operacion} → {codigo}")

    # ================================
    #        DEVOLUCIÓN
    # ================================
    if operacion == "devolucion" and libro:
        libro.prestado = False
        libro.ejemplares_disponibles += 1

        rep_socket.send_json({"status": "ok", "msg": "Devolución recibida"})
        pub_socket.send_string(f"Devolucion {json.dumps(libro.to_dict())}")

    # ================================
    #        RENOVACIÓN
    # ================================
    elif operacion == "renovacion" and libro:
        nueva_fecha = datetime.now() + timedelta(weeks=1)
        rep_socket.send_json({"status": "ok",
                              "msg": f"Renovación hasta {nueva_fecha}"})


        pub_socket.send_string(
            f"Renovacion {json.dumps({'libro': libro.to_dict(), 'fecha_nueva': str(nueva_fecha)})}"
        )

    # ================================
    #        PRÉSTAMO
    # ================================
    elif operacion == "prestamo" and libro:
        try:
            prestamo_socket = context.socket(zmq.REQ)
            prestamo_socket.connect("tcp://localhost:5557")
            prestamo_socket.send_json({"codigo": codigo})

            respuesta = prestamo_socket.recv_json()
            rep_socket.send_json(respuesta)

            prestamo_socket.close()

        except Exception as e:
            rep_socket.send_json({
                "status": "error",
                "msg": f"Error comunicando con actor de préstamo: {e}"
            })

    # ================================
    # CONSULTA DISPONIBILIDAD
    # ================================
    elif operacion == "disponibilidad" and libro:
        rep_socket.send_json({
            "status": "ok",
            "ejemplares_disponibles": libro.ejemplares_disponibles,
            "codigo": libro.codigo,
            "titulo": libro.titulo
        })

    # ================================
    # ERROR: OPERACIÓN O LIBRO NO EXISTE
    # ================================
    else:
        rep_socket.send_json({
            "status": "error",
            "msg": f"Operación inválida o libro '{codigo}' no existe"
        })

    # ================================
    #       REGISTRO DE MÉTRICAS
    # ================================
    t_fin = now()
    tiempo_respuesta = t_fin - t_inicio

    with open("metricas_gc.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            t_inicio,
            t_fin,
            tiempo_respuesta,
            operacion,
            codigo
        ])

    print(f"⏱ Tiempo de respuesta: {tiempo_respuesta:.4f}s")
