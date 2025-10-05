# actores/actor_prestamo.py
import zmq
import json
from common.LibroUsuario import LibroUsuario
from threading import Lock

# Lock para evitar escritura concurrente en libros.txt
archivo_lock = Lock()

# Contexto ZMQ
context = zmq.Context()

# Socket REP para atender solicitudes de préstamo del Gestor de Carga
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://*:5557")  # Puerto exclusivo para préstamos

# Cargar BD simulada desde archivo
libros = {}
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

print("✅ Actor Préstamo iniciado y escuchando solicitudes...")

def guardar_libros():
    """Guarda la BD de libros en data/libros.txt de forma segura"""
    with archivo_lock:
        with open("data/libros.txt", "w", encoding="utf-8") as f:
            for l in libros.values():
                f.write(json.dumps(l.to_dict()) + "\n")

while True:
    try:
        # Recibir solicitud de préstamo del GC
        mensaje = rep_socket.recv_json()
        codigo = mensaje.get("codigo")

        libro = libros.get(codigo)
        if libro:
            if libro.ejemplares_disponibles > 0:
                # Autorizar préstamo
                libro.ejemplares_disponibles -= 1
                libro.prestado = True
                rep_socket.send_json({
                    "status": "ok",
                    "msg": f"Préstamo autorizado para {libro.titulo} por 2 semanas"
                })
                print(f"✅ Préstamo autorizado: {libro.titulo}")
                guardar_libros()
            else:
                # No hay ejemplares disponibles
                rep_socket.send_json({
                    "status": "error",
                    "msg": f"Préstamo DENEGADO: no hay ejemplares disponibles de {libro.titulo}"
                })
                print(f"❌ Préstamo DENEGADO: {libro.titulo}")
        else:
            # Libro no existe
            rep_socket.send_json({
                "status": "error",
                "msg": f"Préstamo DENEGADO: libro con código {codigo} no existe"
            })
            print(f"❌ Préstamo DENEGADO: código {codigo} no existe")

    except json.JSONDecodeError as e:
        print("⚠️ Error al decodificar JSON de solicitud:", e)
        rep_socket.send_json({"status": "error", "msg": "Solicitud inválida"})
