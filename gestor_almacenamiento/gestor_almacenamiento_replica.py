import zmq
import json
import threading
import os
from common.LibroUsuario import LibroUsuario

ARCHIVO_REPLICA = "data/libros_replica.txt"
LOCK = threading.Lock()

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5561")  # Puerto diferente para la réplica

libros = {}

def cargar_datos():
    global libros
    libros = {}
    if os.path.exists(ARCHIVO_REPLICA):
        try:
            with open(ARCHIVO_REPLICA, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        libros[data["codigo"]] = LibroUsuario(**data)
            print("✅ Réplica secundaria cargada y operativa")
            return True
        except Exception as e:
            print(f"❌ Error cargando réplica: {e}")
    return False

cargar_datos()
print("🔄 GESTOR DE ALMACENAMIENTO RÉPLICA iniciado en puerto 5561")

def guardar_datos():
    with LOCK:
        try:
            with open(ARCHIVO_REPLICA, "w", encoding="utf-8") as f:
                for l in libros.values():
                    f.write(json.dumps(l.to_dict()) + "\n")
            print("💾 Datos guardados en réplica secundaria")
        except Exception as e:
            print(f"❌ Error guardando en réplica: {e}")

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
                print(f"📖 Réplica: Enviado libro {codigo}")
            else:
                socket.send_json({"status": "error", "msg": "No encontrado"})

        elif op == "actualizar":
            if codigo in libros:
                for k, v in data.items():
                    setattr(libros[codigo], k, v)
                guardar_datos()
                socket.send_json({"status": "ok", "msg": "Actualizado en réplica"})
                print(f"✅ Réplica: Libro {codigo} actualizado")
            else:
                socket.send_json({"status": "error", "msg": "Código inexistente"})

        else:
            socket.send_json({"status": "error", "msg": "Operación inválida"})

    except Exception as e:
        print(f"❌ Error en réplica: {e}")
        try:
            socket.send_json({"status": "error", "msg": str(e)})
        except:
            pass