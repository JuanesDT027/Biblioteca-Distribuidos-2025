# gestor_almacenamiento/gestor_almacenamiento.py
import zmq
import json
import threading
import time
import os
from common.LibroUsuario import LibroUsuario

ARCHIVO_PRINCIPAL = "data/libros.txt"
ARCHIVO_REPLICA = "data/libros_replica.txt"
LOCK = threading.Lock()

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5560")  # puerto exclusivo para GA

# Cargar datos en memoria
libros = {}
if os.path.exists(ARCHIVO_PRINCIPAL):
    with open(ARCHIVO_PRINCIPAL, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                libros[data["codigo"]] = LibroUsuario(**data)

print("✅ Gestor de Almacenamiento iniciado (GA-Primario)")

def guardar_datos():
    """Guarda los libros en el archivo principal y su réplica."""
    with LOCK:
        with open(ARCHIVO_PRINCIPAL, "w", encoding="utf-8") as f:
            for l in libros.values():
                f.write(json.dumps(l.to_dict()) + "\n")
        with open(ARCHIVO_REPLICA, "w", encoding="utf-8") as f2:
            for l in libros.values():
                f2.write(json.dumps(l.to_dict()) + "\n")
    print("💾 Cambios guardados y replicados correctamente.")

while True:
    mensaje = socket.recv_json()
    operacion = mensaje.get("operacion")
    codigo = mensaje.get("codigo")
    data = mensaje.get("data")

    if operacion == "leer":
        libro = libros.get(codigo)
        if libro:
            socket.send_json({"status": "ok", "libro": libro.to_dict()})
        else:
            socket.send_json({"status": "error", "msg": "Libro no encontrado"})

    elif operacion == "actualizar":
        if codigo in libros:
            with LOCK:
                for clave, valor in data.items():
                    setattr(libros[codigo], clave, valor)
                guardar_datos()
            socket.send_json({"status": "ok", "msg": "Registro actualizado"})
        else:
            socket.send_json({"status": "error", "msg": "Código inexistente"})

    elif operacion == "backup":
        """Envía el contenido completo a un GA secundario o Health Monitor."""
        socket.send_json({
            "status": "ok",
            "backup": [libro.to_dict() for libro in libros.values()]
        })

    elif operacion == "sincronizar":
        """Recibe datos desde otro GA y actualiza la réplica."""
        nuevos_datos = mensaje.get("backup", [])
        if nuevos_datos:
            with LOCK:
                libros.clear()
                for d in nuevos_datos:
                    libros[d["codigo"]] = LibroUsuario(**d)
                guardar_datos()
            socket.send_json({"status": "ok", "msg": "Sincronización completa"})
        else:
            socket.send_json({"status": "error", "msg": "Sin datos para sincronizar"})

    else:
        socket.send_json({"status": "error", "msg": f"Operación '{operacion}' no reconocida"})
