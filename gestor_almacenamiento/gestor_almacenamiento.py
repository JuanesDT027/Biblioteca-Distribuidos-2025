import zmq
import json
import threading
import os
from common.LibroUsuario import LibroUsuario

ARCHIVO_PRINCIPAL = "data/libros.txt"
LOCK = threading.Lock()

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5560")

libros = {}
if os.path.exists(ARCHIVO_PRINCIPAL):
    with open(ARCHIVO_PRINCIPAL, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                libros[data["codigo"]] = LibroUsuario(**data)

print("✅ Gestor de Almacenamiento (GA) operativo.")

def guardar_datos():
    """Guarda los cambios en el archivo principal."""
    with LOCK:
        with open(ARCHIVO_PRINCIPAL, "w", encoding="utf-8") as f:
            for l in libros.values():
                f.write(json.dumps(l.to_dict()) + "\n")
    print("💾 Datos actualizados correctamente en libros.txt")

while True:
    try:
        msg = socket.recv_json()
        op = msg.get("operacion")
        codigo = msg.get("codigo")
        data = msg.get("data")

        if op == "leer":
            libro = libros.get(codigo)
            if libro:
                socket.send_json({"status": "ok", "libro": libro.to_dict()})
                print(f"📖 Enviado libro {codigo}")
            else:
                socket.send_json({"status": "error", "msg": "No encontrado"})
                print(f"❌ Libro {codigo} no encontrado")

        elif op == "actualizar":
            if codigo in libros:
                for k, v in data.items():
                    setattr(libros[codigo], k, v)
                guardar_datos()
                socket.send_json({"status": "ok", "msg": "Actualizado"})
                print(f"✅ Libro {codigo} actualizado")
            else:
                socket.send_json({"status": "error", "msg": "Código inexistente"})
                print(f"⚠️ Código {codigo} inexistente")

        else:
            socket.send_json({"status": "error", "msg": f"Operación '{op}' no válida"})

    except Exception as e:
        print(f"❌ Error GA: {e}")
        try:
            socket.send_json({"status": "error", "msg": str(e)})
        except:
            pass