import zmq
import json
import threading
import os
from common.LibroUsuario import LibroUsuario

ARCHIVO_PRINCIPAL = "data/libros.txt"
ARCHIVO_REPLICA = "data/libros_replica.txt"
LOCK = threading.Lock()

# Crear contexto y socket REP
context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5560")  # Puerto exclusivo para GA

# Cargar BD simulada desde archivo
libros = {}
if os.path.exists(ARCHIVO_PRINCIPAL):
    with open(ARCHIVO_PRINCIPAL, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                libros[data["codigo"]] = LibroUsuario(**data)

print("✅ Gestor de Almacenamiento iniciado (GA-Primario)")

# ===============================
# Guardado directo (principal + réplica)
# ===============================
def guardar_datos():
    """Guarda los libros en el archivo principal y en la réplica."""
    with LOCK:
        # Guardar base principal
        with open(ARCHIVO_PRINCIPAL, "w", encoding="utf-8") as f:
            for l in libros.values():
                f.write(json.dumps(l.to_dict()) + "\n")
            f.flush()

        # Guardar copia de seguridad
        with open(ARCHIVO_REPLICA, "w", encoding="utf-8") as f2:
            for l in libros.values():
                f2.write(json.dumps(l.to_dict()) + "\n")
            f2.flush()

    print("💾 Cambios guardados en la base principal y réplica.")


while True:
    try:
        mensaje = socket.recv_json()
        operacion = mensaje.get("operacion")
        codigo = mensaje.get("codigo")
        data = mensaje.get("data")

        print(f"\n📨 Solicitud recibida: {operacion} (Código: {codigo})")

        # ---- LECTURA ----
        if operacion == "leer":
            libro = libros.get(codigo)
            if libro:
                print(f"📘 Enviando datos de {codigo} al solicitante.")
                socket.send_json({"status": "ok", "libro": libro.to_dict()})
            else:
                socket.send_json({"status": "error", "msg": "Libro no encontrado"})

        # ---- ACTUALIZACIÓN ----
        elif operacion == "actualizar":
            if codigo in libros:
                for clave, valor in data.items():
                    setattr(libros[codigo], clave, valor)
                guardar_datos()  # Guardar directamente
                print(f"✅ Registro {codigo} actualizado y persistido.")
                socket.send_json({"status": "ok", "msg": "Registro actualizado"})
            else:
                socket.send_json({"status": "error", "msg": "Código inexistente"})

        # ---- BACKUP ----
        elif operacion == "backup":
            socket.send_json({
                "status": "ok",
                "backup": [libro.to_dict() for libro in libros.values()]
            })

        # ---- SINCRONIZAR ----
        elif operacion == "sincronizar":
            nuevos_datos = mensaje.get("backup", [])
            if nuevos_datos:
                libros.clear()
                for d in nuevos_datos:
                    libros[d["codigo"]] = LibroUsuario(**d)
                guardar_datos()
                socket.send_json({"status": "ok", "msg": "Sincronización completa"})
            else:
                socket.send_json({"status": "error", "msg": "Sin datos para sincronizar"})

        else:
            socket.send_json({"status": "error", "msg": f"Operación '{operacion}' no reconocida"})

    except Exception as e:
        print(f"❌ Error en GA: {e}")
        try:
            socket.send_json({"status": "error", "msg": str(e)})
        except:
            pass
