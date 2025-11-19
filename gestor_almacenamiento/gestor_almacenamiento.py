import zmq
import json
import threading
import os
from common.LibroUsuario import LibroUsuario

ARCHIVO_PRINCIPAL = "data/libros.txt"
ARCHIVO_REPLICA = "data/libros_replica.txt"
LOCK = threading.Lock()

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5560")

libros = {}
USANDO_REPLICA = False


# ================================
#         CARGA DE DATOS
# ================================
def cargar_datos():
    global libros, USANDO_REPLICA
    libros = {}

    # Intento cargar desde principal
    if os.path.exists(ARCHIVO_PRINCIPAL):
        try:
            with open(ARCHIVO_PRINCIPAL, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        libros[data["codigo"]] = LibroUsuario(**data)
            USANDO_REPLICA = False
            return True
        except:
            pass

    # Fallover → cargar desde replica
    if os.path.exists(ARCHIVO_REPLICA):
        try:
            with open(ARCHIVO_REPLICA, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        libros[data["codigo"]] = LibroUsuario(**data)
            USANDO_REPLICA = True
            return True
        except:
            pass

    return False


cargar_datos()


# ================================
#         GUARDADO
# ================================
def guardar_datos():
    global USANDO_REPLICA

    with LOCK:
        try:
            # Guardar en principal
            with open(ARCHIVO_PRINCIPAL, "w", encoding="utf-8") as f:
                for l in libros.values():
                    f.write(json.dumps(l.to_dict()) + "\n")

            # Guardar en réplica
            with open(ARCHIVO_REPLICA, "w", encoding="utf-8") as f:
                for l in libros.values():
                    f.write(json.dumps(l.to_dict()) + "\n")

            USANDO_REPLICA = False

        except:
            # Guardar sólo en réplica
            try:
                with open(ARCHIVO_REPLICA, "w", encoding="utf-8") as f:
                    for l in libros.values():
                        f.write(json.dumps(l.to_dict()) + "\n")
                USANDO_REPLICA = True
            except:
                pass


# ================================
#        LOOP PRINCIPAL
# ================================
while True:
    try:
        msg = socket.recv_json()
        op = msg.get("operacion")
        codigo = msg.get("codigo")
        data = msg.get("data")

        # -------- LEER --------
        if op == "leer":
            libro = libros.get(codigo)
            if libro:
                socket.send_json({"status": "ok", "libro": libro.to_dict()})
            else:
                socket.send_json({"status": "error", "msg": "No encontrado"})

        # ----- ACTUALIZAR -----
        elif op == "actualizar":
            if codigo in libros:
                for k, v in data.items():
                    setattr(libros[codigo], k, v)
                guardar_datos()
                socket.send_json({"status": "ok", "msg": "Actualizado"})
            else:
                socket.send_json({"status": "error", "msg": "Código inexistente"})

        else:
            socket.send_json({"status": "error", "msg": "Operación inválida"})

    except Exception as e:
        try:
            socket.send_json({"status": "error", "msg": str(e)})
        except:
            pass