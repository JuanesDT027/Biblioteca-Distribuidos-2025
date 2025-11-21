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
socket.bind("tcp://*:5561")  # Réplica en puerto 5561

# Variable global para indicar si este GA es primario o réplica
ES_PRIMARIO = False
libros = {}

def cargar_datos():
    global libros
    libros = {}
   
    # La réplica siempre carga desde su archivo de réplica
    if os.path.exists(ARCHIVO_REPLICA):
        try:
            with open(ARCHIVO_REPLICA, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        libros[data["codigo"]] = LibroUsuario(**data)
            print("🔄 RÉPLICA: Datos cargados desde archivo de réplica")
            return True
        except Exception as e:
            print(f"❌ RÉPLICA: Error cargando réplica: {e}")
   
    return False

# Cargar datos al inicio
if cargar_datos():
    print("✅ Gestor de Almacenamiento RÉPLICA operativo en puerto 5561")
else:
    print("❌ RÉPLICA: No se pudieron cargar datos")
    libros = {}

def guardar_datos():
    """Guarda los cambios solo en la réplica."""
    with LOCK:
        try:
            # Réplica solo guarda en su archivo
            with open(ARCHIVO_REPLICA, "w", encoding="utf-8") as f:
                for l in libros.values():
                    f.write(json.dumps(l.to_dict()) + "\n")
                   
            print("💾 RÉPLICA: Datos actualizados en réplica secundaria")
           
        except Exception as e:
            print(f"❌ RÉPLICA: Error crítico guardando datos: {e}")

print("🔄 GA Réplica iniciado en 10.43.102.150:5561 - Esperando failover...")

while True:
    try:
        msg = socket.recv_json()
        op = msg.get("operacion")
        codigo = msg.get("codigo")
        data = msg.get("data")

        if op == "leer":
            libro = libros.get(codigo)
            if libro:
                socket.send_json({"status": "ok", "libro": libro.to_dict(), "replica": not ES_PRIMARIO})
                print(f"📖 RÉPLICA: Enviado libro {codigo}")
            else:
                socket.send_json({"status": "error", "msg": "No encontrado", "replica": not ES_PRIMARIO})
                print(f"❌ RÉPLICA: Libro {codigo} no encontrado")

        elif op == "actualizar":
            if codigo in libros:
                for k, v in data.items():
                    setattr(libros[codigo], k, v)
                guardar_datos()
                socket.send_json({"status": "ok", "msg": "Actualizado", "replica": not ES_PRIMARIO})
                print(f"✅ RÉPLICA: Libro {codigo} actualizado")
            else:
                socket.send_json({"status": "error", "msg": "Código inexistente", "replica": not ES_PRIMARIO})
                print(f"⚠️ RÉPLICA: Código {codigo} inexistente")

        else:
            socket.send_json({"status": "error", "msg": f"Operación '{op}' no válida", "replica": not ES_PRIMARIO})

    except Exception as e:
        print(f"❌ RÉPLICA: Error: {e}")
        try:
            socket.send_json({"status": "error", "msg": str(e), "replica": not ES_PRIMARIO})
        except:
            pass