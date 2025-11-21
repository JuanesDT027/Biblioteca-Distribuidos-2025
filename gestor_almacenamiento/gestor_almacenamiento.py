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
            print("🔄 FALLOVER ACTIVADO: Cargando desde réplica")
            return True
        except Exception as e:
            print(f"❌ Error cargando réplica: {e}")
   
    return False

def guardar_datos():
    with LOCK:
        try:
            with open(ARCHIVO_PRINCIPAL, "w", encoding="utf-8") as f:
                for l in libros.values():
                    f.write(json.dumps(l.to_dict()) + "\n")
           
            with open(ARCHIVO_REPLICA, "w", encoding="utf-8") as f:
                for l in libros.values():
                    f.write(json.dumps(l.to_dict()) + "\n")
                   
            print("💾 Datos actualizados en archivo principal y réplica")
           
        except Exception as e:
            print(f"⚠️ Error guardando: {e}")

# Cargar datos al inicio
if cargar_datos():
    print("✅ Gestor de Almacenamiento (GA) PRIMARIO operativo en puerto 5560")
else:
    print("❌ No se pudieron cargar datos")
    libros = {}

print("🚀 GA Primario iniciado - Listo para conexiones...")

while True:
    try:
        msg = socket.recv_json()
        op = msg.get("operacion")
        codigo = msg.get("codigo")
        data = msg.get("data")

        # Operación LISTAR para health check
        if op == "listar":
            socket.send_json({
                "status": "ok", 
                "libros": {k: v.to_dict() for k, v in libros.items()}, 
                "total": len(libros),
                "replica": not ES_PRIMARIO
            })
            continue

        if op == "leer":
            libro = libros.get(codigo)
            if libro:
                socket.send_json({
                    "status": "ok", 
                    "libro": libro.to_dict(), 
                    "replica": not ES_PRIMARIO
                })
                print(f"📖 Enviado libro {codigo}")
            else:
                socket.send_json({
                    "status": "error", 
                    "msg": "No encontrado", 
                    "replica": not ES_PRIMARIO
                })

        elif op == "actualizar":
            if codigo in libros:
                for k, v in data.items():
                    setattr(libros[codigo], k, v)
                guardar_datos()
                socket.send_json({
                    "status": "ok", 
                    "msg": "Actualizado", 
                    "replica": not ES_PRIMARIO
                })
                print(f"✅ Libro {codigo} actualizado")
            else:
                socket.send_json({
                    "status": "error", 
                    "msg": "Código inexistente", 
                    "replica": not ES_PRIMARIO
                })

        else:
            socket.send_json({
                "status": "error", 
                "msg": f"Operación '{op}' no válida", 
                "replica": not ES_PRIMARIO
            })

    except Exception as e:
        print(f"❌ Error GA: {e}")
        try:
            socket.send_json({
                "status": "error", 
                "msg": str(e), 
                "replica": not ES_PRIMARIO
            })
        except:
            pass