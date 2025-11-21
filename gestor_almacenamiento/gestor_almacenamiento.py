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
socket.bind("tcp://*:5560")  # GA Primario en puerto 5560

# Variable global para indicar si este GA es primario o réplica
ES_PRIMARIO = True
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
            print("✅ Datos cargados desde archivo principal")
            return True
        except Exception as e:
            print(f"⚠️ Error cargando archivo principal: {e}")
   
    if os.path.exists(ARCHIVO_REPLICA):
        try:
            with open(ARCHIVO_REPLICA, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        libros[data["codigo"]] = LibroUsuario(**data)
            print("🔄 FALLOVER ACTIVADO: Cargando datos desde réplica secundaria")
            print("🚨 SISTEMA CONTINÚA OPERANDO CON RÉPLICA - Failover exitoso")
            return True
        except Exception as e:
            print(f"❌ Error cargando réplica secundaria: {e}")
   
    return False

# Cargar datos al inicio
if cargar_datos():
    print("✅ Gestor de Almacenamiento (GA) PRIMARIO operativo en puerto 5560")
else:
    print("❌ No se pudieron cargar datos ni del archivo principal ni de la réplica")
    libros = {}

def guardar_datos():
    """Guarda los cambios en el archivo principal y réplica."""
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
                   
            print("💾 Datos actualizados correctamente en archivo principal y réplica")
           
        except Exception as e:
            print(f"⚠️ Error guardando en archivo principal: {e}")
            print("🔄 Intentando guardar solo en réplica secundaria...")
           
            try:
                # Fallback: guardar solo en réplica
                with open(ARCHIVO_REPLICA, "w", encoding="utf-8") as f:
                    for l in libros.values():
                        f.write(json.dumps(l.to_dict()) + "\n")
                print("✅ Datos guardados en réplica secundaria (modo degradado)")
            except Exception as e2:
                print(f"❌ Error crítico: No se pudo guardar en ninguna réplica: {e2}")

print("🚀 GA Primario iniciado en 10.43.102.150:5560 - Listo para conexiones...")

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
                print(f"📖 Enviado libro {codigo} desde {'RÉPLICA' if not ES_PRIMARIO else 'PRIMARIO'}")
            else:
                socket.send_json({"status": "error", "msg": "No encontrado", "replica": not ES_PRIMARIO})
                print(f"❌ Libro {codigo} no encontrado")

        elif op == "actualizar":
            if codigo in libros:
                for k, v in data.items():
                    setattr(libros[codigo], k, v)
                guardar_datos()
                socket.send_json({"status": "ok", "msg": "Actualizado", "replica": not ES_PRIMARIO})
                print(f"✅ Libro {codigo} actualizado en {'RÉPLICA' if not ES_PRIMARIO else 'PRIMARIO'}")
            else:
                socket.send_json({"status": "error", "msg": "Código inexistente", "replica": not ES_PRIMARIO})
                print(f"⚠️ Código {codigo} inexistente")

        else:
            socket.send_json({"status": "error", "msg": f"Operación '{op}' no válida", "replica": not ES_PRIMARIO})

    except Exception as e:
        print(f"❌ Error GA: {e}")
        try:
            socket.send_json({"status": "error", "msg": str(e), "replica": not ES_PRIMARIO})
        except:
            pass