import time
import zmq
import json
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

# Contexto ZMQ
context = zmq.Context()

# Socket REP para recibir solicitudes de PS
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://*:5555")

time.sleep(1)
# Socket PUB para notificar a los actores
pub_socket = context.socket(zmq.PUB)
pub_socket.bind("tcp://*:5556")  

# BD simulada
libros = {}  # Diccionario: clave=codigo, valor=LibroUsuario

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
print("✅ Gestor de Carga iniciado, esperando solicitudes...")

while True:
    mensaje_raw = rep_socket.recv_json()
    operacion = mensaje_raw.get("operacion")
    codigo = mensaje_raw.get("codigo")
    
    libro = libros.get(codigo)
    print("Operación recibida:", operacion)

    # Devolución
    if operacion == "devolucion" and libro:
        libro.prestado = False
        libro.ejemplares_disponibles += 1
        rep_socket.send_json({"status": "ok", "msg": "Devolución recibida"})
        pub_socket.send_string(f"Devolucion {json.dumps(libro.to_dict())}")

    # Renovación
    elif operacion == "renovacion" and libro:
        nueva_fecha = datetime.now() + timedelta(weeks=1)
        rep_socket.send_json({"status": "ok", "msg": f"Renovación hasta {nueva_fecha}"})
        pub_socket.send_string(
            f"Renovacion {json.dumps({'libro': libro.to_dict(), 'fecha_nueva': str(nueva_fecha)})}"
        )

    # Préstamo
    elif operacion == "prestamo" and libro:
        try:
            prestamo_socket = context.socket(zmq.REQ)
            prestamo_socket.connect("tcp://localhost:5557")
            prestamo_socket.send_json({"codigo": codigo})
            respuesta = prestamo_socket.recv_json()
            rep_socket.send_json(respuesta)
            prestamo_socket.close()
            print("📨 Respuesta del Actor de Préstamo:", respuesta["msg"])
        except Exception as e:
            rep_socket.send_json({"status": "error", "msg": f"Error comunicando con actor de préstamo: {e}"})

   # **Nueva operación: consultar disponibilidad**
    elif operacion == "disponibilidad" and libro:
        rep_socket.send_json({
            "status": "ok",
            "ejemplares_disponibles": libro.ejemplares_disponibles,
            "codigo": libro.codigo,
            "titulo": libro.titulo
        })
    # Código de libro inválido o operación inválida
    else:
        rep_socket.send_json({
            "status": "error",
            "msg": f"Operación inválida o libro con código '{codigo}' no existe"
        })
