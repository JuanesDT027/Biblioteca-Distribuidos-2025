import zmq
import json
import threading
import os
import time
from common.LibroUsuario import LibroUsuario

ARCHIVO_REPLICA = "data/libros_replica.txt"
LOCK = threading.Lock()

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5561")  # Puerto diferente para la réplica

libros = {}
REPLICA_ACTIVA = False

def cargar_datos_desde_principal():
    """Intenta cargar datos desde el GA principal"""
    global libros
    ARCHIVO_PRINCIPAL = "data/libros.txt"
    
    if os.path.exists(ARCHIVO_PRINCIPAL):
        try:
            libros = {}
            with open(ARCHIVO_PRINCIPAL, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        libros[data["codigo"]] = LibroUsuario(**data)
            print("✅ Réplica: Datos sincronizados desde GA principal")
            return True
        except Exception as e:
            print(f"⚠️ Réplica: Error sincronizando con principal: {e}")
    
    # Si no hay principal, cargar desde réplica
    if os.path.exists(ARCHIVO_REPLICA):
        try:
            libros = {}
            with open(ARCHIVO_REPLICA, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        libros[data["codigo"]] = LibroUsuario(**data)
            print("✅ Réplica: Datos cargados desde archivo de réplica")
            return True
        except Exception as e:
            print(f"❌ Réplica: Error cargando réplica: {e}")
    
    return False

def verificar_principal_activo():
    """Verifica si el GA principal está activo"""
    try:
        test_socket = context.socket(zmq.REQ)
        test_socket.setsockopt(zmq.LINGER, 0)
        test_socket.RCVTIMEO = 2000
        test_socket.connect("tcp://localhost:5560")
        test_socket.send_json({"operacion": "ping"})
        test_socket.recv_json()
        test_socket.close()
        return True
    except:
        return False

# Cargar datos iniciales
if cargar_datos_desde_principal():
    print("✅ Gestor de Almacenamiento Réplica listo (modo standby)")
else:
    print("❌ Réplica: No se pudieron cargar datos iniciales")
    libros = {}

def guardar_datos():
    """Guarda los cambios en el archivo de réplica"""
    with LOCK:
        try:
            with open(ARCHIVO_REPLICA, "w", encoding="utf-8") as f:
                for l in libros.values():
                    f.write(json.dumps(l.to_dict()) + "\n")
            print("💾 Réplica: Datos guardados en archivo de réplica")
        except Exception as e:
            print(f"❌ Réplica: Error guardando datos: {e}")

# ================================
#        LOOP PRINCIPAL
# ================================
while True:
    # Verificar si debemos activarnos como primarios
    principal_activo = verificar_principal_activo()
    
    if not principal_activo and not REPLICA_ACTIVA:
        REPLICA_ACTIVA = True
        print("🔄 FALLOVER AUTOMÁTICO: Réplica secundaria ACTIVADA como primaria")
        print("📍 Ahora operando desde Sede B - Servicio continuo garantizado")
    
    elif principal_activo and REPLICA_ACTIVA:
        REPLICA_ACTIVA = False
        print("🔙 Retornando a modo standby - GA principal recuperado")
        # Resincronizar datos desde principal
        cargar_datos_desde_principal()
    
    try:
        # Solo procesar solicitudes si estamos activos o el principal está caído
        if not principal_activo or REPLICA_ACTIVA:
            socket.RCVTIMEO = 1000  # Timeout corto para no bloquear
            msg = socket.recv_json()
            
            op = msg.get("operacion")
            codigo = msg.get("codigo")
            data = msg.get("data")

            if REPLICA_ACTIVA:
                print(f"📍 Réplica Activa procesando: {op} -> {codigo}")

            # -------- LEER --------
            if op == "leer":
                libro = libros.get(codigo)
                if libro:
                    socket.send_json({"status": "ok", "libro": libro.to_dict()})
                    if REPLICA_ACTIVA:
                        print(f"📖 Réplica: Enviado libro {codigo}")
                else:
                    socket.send_json({"status": "error", "msg": "No encontrado"})

            # ----- ACTUALIZAR -----
            elif op == "actualizar":
                if codigo in libros:
                    for k, v in data.items():
                        setattr(libros[codigo], k, v)
                    guardar_datos()
                    socket.send_json({"status": "ok", "msg": "Actualizado"})
                    if REPLICA_ACTIVA:
                        print(f"✅ Réplica: Libro {codigo} actualizado")
                else:
                    socket.send_json({"status": "error", "msg": "Código inexistente"})

            elif op == "ping":
                socket.send_json({"status": "ok", "msg": "pong"})

            else:
                socket.send_json({"status": "error", "msg": "Operación inválida"})
        else:
            # Modo standby - no procesar solicitudes
            time.sleep(1)
            
    except zmq.Again:
        # Timeout - continuar verificando estado
        continue
    except Exception as e:
        try:
            socket.send_json({"status": "error", "msg": str(e)})
        except:
            pass