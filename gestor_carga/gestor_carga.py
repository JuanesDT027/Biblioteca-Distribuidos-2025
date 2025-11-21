import time
import zmq
import json
import csv
import os
from time import time as now
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

# ======================================================
#                CONFIGURACIÓN DEL MODO
# ======================================================

# MODO_METRICAS = "multihilo"
MODO_METRICAS = "serial"     

# ======================================================
#  CONFIGURACIÓN ZMQ Y FAILOVER
# ======================================================

context = zmq.Context()

# REP → recibe solicitudes de los PS
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://*:5555")

time.sleep(1)

# PUB → envía eventos a actores
pub_socket = context.socket(zmq.PUB)
pub_socket.bind("tcp://*:5556")

# ======================================================
# CONFIGURACIÓN FAILOVER GA Y CONEXIONES
# ======================================================

GA_PRIMARIO = "tcp://localhost:5560"
GA_REPLICA = "tcp://localhost:5561"
ga_actual = GA_PRIMARIO

# IP del actor préstamo en PC local
ACTOR_PRESTAMO_IP = "tcp://192.168.10.10:5557"

# ======================================================
# BASE DE DATOS SIMULADA
# ======================================================

libros = {}

def cargar_libros():
    with open("data/libros.txt", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                libros[data["codigo"]] = LibroUsuario(**data)
            except:
                print("⚠️ Error leyendo línea:", line)

cargar_libros()
print("✅ Gestor de Carga iniciado y listo para recibir solicitudes...")
print(f"📡 Conectando a Actor Préstamo en: {ACTOR_PRESTAMO_IP}")

# ======================================================
#   FUNCIONES DE FAILOVER - CORREGIDAS
# ======================================================

def conectar_ga():
    """Conecta al GA actual y maneja failover automático"""
    global ga_actual
    
    ga_socket = context.socket(zmq.REQ)
    ga_socket.setsockopt(zmq.LINGER, 0)
    ga_socket.RCVTIMEO = 3000  # Timeout reducido para failover rápido
    ga_socket.SNDTIMEO = 3000
    
    try:
        ga_socket.connect(ga_actual)
        return ga_socket
    except Exception as e:
        print(f"❌ Error conectando a GA en {ga_actual}: {e}")
        return None

def verificar_disponibilidad_ga():
    """Verifica si el GA actual está disponible - CORREGIDA"""
    global ga_actual
    
    ga_socket = conectar_ga()
    if not ga_socket:
        return False
    
    try:
        
        ga_socket.send_json({"operacion": "ping", "mensaje": "health_check"})
        respuesta = ga_socket.recv_json()
        
        # El GA está disponible si responde
        print(f"✅ GA {ga_actual} está disponible")
        return True
        
    except zmq.Again:
        print(f"⏰ Timeout - GA {ga_actual} no responde")
        return False
    except Exception as e:
        print(f"⚠️ Error verificando GA {ga_actual}: {e}")
        return False
    finally:
        if ga_socket:
            ga_socket.close()

def realizar_failover_si_necesario():
    """Realiza failover automático si el GA primario no responde - CORREGIDA"""
    global ga_actual
    
    if ga_actual == GA_PRIMARIO:
        print(f"🔍 Verificando disponibilidad del GA primario...")
        if not verificar_disponibilidad_ga():
            print("🔄 DETECTANDO FALLO DEL GA PRIMARIO - INICIANDO FALLOVER...")
            ga_actual = GA_REPLICA
            print("✅ FAILOVER COMPLETADO - Usando RÉPLICA SECUNDARIA")
            return True
        else:
            print("✅ GA Primario está disponible")
    return False

# ======================================================
#   CONFIGURACIÓN ARCHIVO DE MÉTRICAS (SERIAL o MULTIHILO)
# ======================================================

if MODO_METRICAS == "serial":
    # Crear carpeta Serial si no existe
    os.makedirs("data/Serial", exist_ok=True)

    # SOLO descomenta la prueba que estás haciendo
    NOMBRE_METRICAS = "data/Serial/metricas5Solicitudes_Serial.csv"
    #NOMBRE_METRICAS = "data/Serial/metricas10Solicitudes_Serial.csv"
    #NOMBRE_METRICAS = "data/Serial/metricas20Solicitudes_Serial.csv"

else:  # MULTIHILO (como antes)
    # SOLO descomenta la prueba multihilo correspondiente
    NOMBRE_METRICAS = "data/metricas5Solicitudes_Multihilo.csv"
    #NOMBRE_METRICAS = "data/metricas10Solicitudes_Multihilo.csv"
    #NOMBRE_METRICAS = "data/metricas20Solicitudes_Multihilo.csv"

# Crear archivo CSV
with open(NOMBRE_METRICAS, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp_llegada",
        "timestamp_salida",
        "tiempo_respuesta",
        "operacion",
        "codigo",
        "replica_utilizada"  # Nueva columna para métricas de failover
    ])

print(f"📁 Guardando métricas en: {NOMBRE_METRICAS}")

# ======================================================
#                   BUCLE PRINCIPAL
# ======================================================

while True:
    t_inicio = now()

    mensaje_raw = rep_socket.recv_json()
    operacion = mensaje_raw.get("operacion")
    codigo = mensaje_raw.get("codigo")

    libro = libros.get(codigo)
    print(f"\n📩 Operación recibida: {operacion} → {codigo}")

    # Verificar failover antes de procesar la operación
    replica_utilizada = realizar_failover_si_necesario() or (ga_actual == GA_REPLICA)

    # DEVOLUCIÓN
    if operacion == "devolucion" and libro:
        libro.prestado = False
        libro.ejemplares_disponibles += 1

        mensaje_respuesta = "Devolución recibida"
        if replica_utilizada:
            mensaje_respuesta += " [Procesado en RÉPLICA SECUNDARIA - FAILOVER]"

        rep_socket.send_json({"status": "ok", "msg": mensaje_respuesta})
        pub_socket.send_string(f"Devolucion {json.dumps(libro.to_dict())}")

    # RENOVACIÓN
    elif operacion == "renovacion" and libro:
        nueva_fecha = datetime.now() + timedelta(weeks=1)

        mensaje_respuesta = f"Renovación hasta {nueva_fecha}"
        if replica_utilizada:
            mensaje_respuesta += " [Procesado en RÉPLICA SECUNDARIA - FAILOVER]"

        rep_socket.send_json({
            "status": "ok",
            "msg": mensaje_respuesta
        })

        pub_socket.send_string(
            f"Renovacion {json.dumps({'libro': libro.to_dict(), 'fecha_nueva': str(nueva_fecha)})}"
        )

    # PRÉSTAMO
    elif operacion == "prestamo" and libro:
        prestamo_socket = None
        try:
            prestamo_socket = context.socket(zmq.REQ)
            prestamo_socket.setsockopt(zmq.LINGER, 0)
            prestamo_socket.RCVTIMEO = 10000  # Aumentado a 10 segundos
            prestamo_socket.SNDTIMEO = 5000
            
            # CORRECCIÓN: Conectar a la IP del PC local donde está el actor préstamo
            prestamo_socket.connect(ACTOR_PRESTAMO_IP)
            print(f"🔗 Conectado a Actor Préstamo en: {ACTOR_PRESTAMO_IP}")

            # Agregar información de failover al mensaje para el actor
            mensaje_prestamo = {"operacion": "prestamo", "codigo": codigo}
            if replica_utilizada:
                mensaje_prestamo["failover_activo"] = True

            prestamo_socket.send_json(mensaje_prestamo)
            print(f"📤 Enviando préstamo a actor: {mensaje_prestamo}")

            try:
                respuesta = prestamo_socket.recv_json()
                print(f"📥 Respuesta del actor préstamo: {respuesta}")
                
                # Agregar información de réplica si es necesario
                if replica_utilizada and respuesta["status"] == "ok":
                    respuesta["msg"] += " [Operación realizada en RÉPLICA SECUNDARIA - FAILOVER EXITOSO]"
                
                rep_socket.send_json(respuesta)
            except zmq.Again:
                error_msg = "Timeout actor préstamo - No respondió en 10 segundos"
                if replica_utilizada:
                    error_msg += " [Intentado en RÉPLICA SECUNDARIA]"
                print(f"⏰ {error_msg}")
                rep_socket.send_json({"status": "error", "msg": error_msg})

        except Exception as e:
            error_msg = str(e)
            if replica_utilizada:
                error_msg += " [Intentado en RÉPLICA SECUNDARIA]"
            print(f"❌ Error conectando con actor préstamo: {error_msg}")
            rep_socket.send_json({"status": "error", "msg": error_msg})
        finally:
            if prestamo_socket:
                prestamo_socket.close()

    # DISPONIBILIDAD
    elif operacion == "disponibilidad" and libro:
        mensaje_respuesta = {
            "status": "ok",
            "ejemplares_disponibles": libro.ejemplares_disponibles,
            "codigo": libro.codigo,
            "titulo": libro.titulo
        }
        
        if replica_utilizada:
            mensaje_respuesta["msg"] = "Consulta realizada en RÉPLICA SECUNDARIA - FAILOVER"
        
        rep_socket.send_json(mensaje_respuesta)

    # ERROR
    else:
        error_msg = f"Operación inválida o libro '{codigo}' no existe"
        if replica_utilizada:
            error_msg += " [Consultado en RÉPLICA SECUNDARIA]"
            
        rep_socket.send_json({
            "status": "error",
            "msg": error_msg
        })

    # REGISTRO MÉTRICAS
    t_fin = now()
    tiempo_respuesta = t_fin - t_inicio

    with open(NOMBRE_METRICAS, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            t_inicio,
            t_fin,
            tiempo_respuesta,
            operacion,
            codigo,
            "REPLICA" if replica_utilizada else "PRIMARIO"  # Nueva métrica
        ])

    print(f"⏱ Tiempo de respuesta: {tiempo_respuesta:.4f}s")
    if replica_utilizada:
        print("🔄 OPERACIÓN REALIZADA EN RÉPLICA SECUNDARIA - FAILOVER ACTIVO")