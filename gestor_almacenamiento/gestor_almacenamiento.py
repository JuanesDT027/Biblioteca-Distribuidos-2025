import zmq
import json
import threading
import os
import time
from common.LibroUsuario import LibroUsuario

ARCHIVO_PRINCIPAL = "data/libros.txt"
ARCHIVO_REPLICA = "data/libros_replica.txt"
LOCK = threading.Lock()

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5560")

libros = {}

def cargar_datos():
    global libros
    libros = {}
    
    if os.path.exists(ARCHIVO_PRINCIPAL):
        try:
            with open(ARCHIVO_PRINCIPAL, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        libros[data["codigo"]] = LibroUsuario(**data)
            print("✅ GA Principal: Datos cargados desde archivo principal")
            return True
        except Exception as e:
            print(f"⚠️ GA Principal: Error cargando archivo principal: {e}")
    
    return False

def guardar_datos():
    """Guarda los cambios en el archivo principal y réplica"""
    with LOCK:
        try:
            # Guardar en archivo principal
            with open(ARCHIVO_PRINCIPAL, "w", encoding="utf-8") as f:
                for l in libros.values():
                    f.write(json.dumps(l.to_dict()) + "\n")
            
            # Replicar en archivo secundario
            with open(ARCHIVO_REPLICA, "w", encoding="utf-8") as f:
                for l in libros.values():
                    f.write(json.dumps(l.to_dict()) + "\n")
                    
            print("💾 GA Principal: Datos actualizados en principal y réplica")
            
        except Exception as e:
            print(f"❌ GA Principal: Error guardando datos: {e}")

# Cargar datos al inicio
if cargar_datos():
    print("✅ Gestor de Almacenamiento Principal operativo.")
else:
    print("❌ GA Principal: No se pudieron cargar datos iniciales")
    libros = {}

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
                print(f"📖 GA Principal: Enviado libro {codigo}")
            else:
                socket.send_json({"status": "error", "msg": "No encontrado"})
                print(f"❌ GA Principal: Libro {codigo} no encontrado")

        elif op == "actualizar":
            if codigo in libros:
                for k, v in data.items():
                    setattr(libros[codigo], k, v)
                guardar_datos()
                socket.send_json({"status": "ok", "msg": "Actualizado"})
                print(f"✅ Libro {codigo} actualizado")
            else:
                socket.send_json({"status": "error", "msg": "Código inexistente"})
                print(f"⚠️ GA Principal: Código {codigo} inexistente")

        elif op == "ping":
            socket.send_json({"status": "ok", "msg": "pong"})

        else:
            socket.send_json({"status": "error", "msg": f"Operación '{op}' no válida"})

    except Exception as e:
        print(f"❌ Error GA Principal: {e}")
        try:
            socket.send_json({"status": "error", "msg": str(e)})
        except:
            pass