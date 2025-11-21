import zmq
import json
import time
from datetime import datetime, timedelta
from common.LibroUsuario import LibroUsuario

# ===============================
#   CONFIG ZMQ Y FAILOVER
# ===============================
context = zmq.Context()

# REP: recibe solicitudes del Gestor de Carga (en máquina virtual)
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://0.0.0.0:5557")  # Actor préstamo escucha en PC local
rep_socket.setsockopt(zmq.LINGER, 0)

# Configuración de GA primario y réplica (ambos en máquina virtual 10.43.102.150)
GA_PRIMARIO = "tcp://10.43.102.150:5560"
GA_REPLICA = "tcp://10.43.102.150:5561"
ga_actual = GA_PRIMARIO

print("✅ Actor Préstamo iniciado en 192.168.10.10:5557")
print("📡 Conectado a GA en 10.43.102.150 - Listo para solicitudes...\n")

def conectar_ga():
    """Conecta al GA actual con failover automático"""
    global ga_actual
    
    print(f"🔗 [DEBUG] Intentando conectar a GA: {ga_actual}")
    ga_socket = context.socket(zmq.REQ)
    ga_socket.setsockopt(zmq.LINGER, 0)
    ga_socket.RCVTIMEO = 5000  # 5 segundos timeout
    ga_socket.SNDTIMEO = 5000
    
    try:
        ga_socket.connect(ga_actual)
        print(f"✅ [DEBUG] Conexión exitosa a GA: {ga_actual}")
        return ga_socket
    except Exception as e:
        print(f"❌ [DEBUG] Error conectando a GA en {ga_actual}: {e}")
        return None

def operacion_ga(operacion, datos):
    """Realiza operación en GA con failover - CON DEBUG DETALLADO"""
    global ga_actual
    
    print(f"🔄 [DEBUG] Ejecutando operación '{operacion}' en GA {ga_actual}")
    print(f"📦 [DEBUG] Datos a enviar al GA: {datos}")
    
    ga_socket = conectar_ga()
    if not ga_socket:
        print("❌ [DEBUG] No se pudo obtener socket GA")
        return {"status": "error", "msg": "No se pudo conectar al GA"}
    
    try:
        datos["operacion"] = operacion
        print(f"📤 [DEBUG] Enviando datos a GA: {datos}")
        ga_socket.send_json(datos)
        print("✅ [DEBUG] Datos enviados exitosamente al GA")
        
        try:
            print("⏳ [DEBUG] Esperando respuesta del GA...")
            respuesta = ga_socket.recv_json()
            print(f"📥 [DEBUG] Respuesta recibida del GA: {respuesta}")
            return respuesta
            
        except zmq.Again:
            print(f"⏰ [DEBUG] TIMEOUT - GA {ga_actual} no respondió en 5 segundos")
            
            # Failover automático
            if ga_actual == GA_PRIMARIO:
                print("🔄 [DEBUG] REALIZANDO FALLOVER A RÉPLICA SECUNDARIA...")
                ga_actual = GA_REPLICA
                ga_socket.close()
                
                # Reintentar con réplica
                print(f"🔄 [DEBUG] Reintentando operación en réplica {ga_actual}...")
                ga_socket = conectar_ga()
                if ga_socket:
                    print(f"📤 [DEBUG] Reenviando datos a réplica: {datos}")
                    ga_socket.send_json(datos)
                    try:
                        print("⏳ [DEBUG] Esperando respuesta de la réplica...")
                        respuesta = ga_socket.recv_json()
                        print(f"📥 [DEBUG] Respuesta de réplica: {respuesta}")
                        return respuesta
                    except zmq.Again:
                        print("⏰ [DEBUG] TIMEOUT - Réplica tampoco respondió")
                        return {"status": "error", "msg": "Timeout en réplica también"}
                else:
                    print("❌ [DEBUG] No se pudo conectar a la réplica")
                    return {"status": "error", "msg": "No se pudo conectar a la réplica"}
            else:
                print("❌ [DEBUG] Ya estábamos en réplica y tampoco respondió")
                return {"status": "error", "msg": "Timeout en réplica secundaria"}
                
    except Exception as e:
        print(f"❌ [DEBUG] Error de comunicación con GA: {e}")
        return {"status": "error", "msg": f"Error de comunicación: {str(e)}"}
    finally:
        if ga_socket:
            ga_socket.close()
            print("🔌 [DEBUG] Socket GA cerrado")

# ===============================
#   LOOP PRINCIPAL CON DEBUG DETALLADO
# ===============================
while True:
    try:
        print("\n" + "="*60)
        print("⏳ [MAIN] ESPERANDO SOLICITUD DE PRÉSTAMO DEL GESTOR DE CARGA...")
        mensaje = rep_socket.recv_json()
        print(f"🎯 [MAIN] SOLICITUD RECIBIDA DEL GC: {mensaje}")

        if not isinstance(mensaje, dict):
            print("❌ [MAIN] Mensaje no es JSON válido")
            rep_socket.send_json({"status": "error", "msg": "Mensaje no es JSON válido"})
            continue

        operacion = mensaje.get("operacion")
        codigo_recibido = mensaje.get("codigo")  # ✅ Variable renombrada para claridad
        failover_activo = mensaje.get("failover_activo", False)

        if operacion != "prestamo":
            print(f"❌ [MAIN] Operación inválida: {operacion}")
            rep_socket.send_json({"status": "error", "msg": f"Operación inválida: {operacion}"})
            continue

        if codigo_recibido is None:
            print("❌ [MAIN] Mensaje inválido: falta 'codigo'")
            rep_socket.send_json({"status": "error", "msg": "Mensaje inválido: falta 'codigo'"})
            continue

        print(f"📚 [MAIN] INICIANDO PROCESAMIENTO DE PRÉSTAMO para código: {codigo_recibido}")
        print(f"🔍 [MAIN] Código recibido del GC: '{codigo_recibido}'")  # ✅ Log adicional para debug
        if failover_activo:
            print("🔄 [MAIN] FAILOVER ACTIVO - Usando réplica secundaria")

        # ===============================
        #   PASO 1: Leer libro en GA (con failover) - CORREGIDO
        # ===============================
        print(f"➡ [PASO 1] Solicitando libro '{codigo_recibido}' al GA...")
        
        # ✅ CORREGIDO: Usar el código recibido del GC, no uno hardcodeado
        datos_lectura = {"codigo": codigo_recibido}
        respuesta = operacion_ga("leer", datos_lectura)
        
        if respuesta["status"] != "ok":
            print(f"❌ [PASO 1] ERROR en lectura GA: {respuesta}")
            
            # Agregar información de réplica al mensaje de error
            error_msg = respuesta.get("msg", "Error desconocido")
            if ga_actual == GA_REPLICA:
                error_msg += " [Intentado en RÉPLICA SECUNDARIA]"
                
            print(f"📤 [MAIN] Enviando error al GC: {error_msg}")
            rep_socket.send_json({"status": "error", "msg": error_msg})
            print("✅ [MAIN] Respuesta de error enviada al GC")
            continue

        libro = LibroUsuario(**respuesta["libro"])
        print(f"✅ [PASO 1] Libro obtenido: {libro.titulo} - Ejemplares disponibles: {libro.ejemplares_disponibles}")
        print(f"🔍 [PASO 1] Código del libro obtenido: {libro.codigo}")  # ✅ Verificar código

        # ===============================
        #   PASO 2: Validar disponibilidad
        # ===============================
        print(f"➡ [PASO 2] Validando disponibilidad...")
        if libro.ejemplares_disponibles <= 0:
            msg = f"❌ Sin ejemplares disponibles de '{libro.titulo}'"
            if ga_actual == GA_REPLICA:
                msg += " [Consultado en RÉPLICA SECUNDARIA]"
            print(f"❌ [PASO 2] {msg}")
            rep_socket.send_json({"status": "error", "msg": msg})
            print("✅ [MAIN] Respuesta de no-disponibilidad enviada al GC")
            continue

        print(f"✅ [PASO 2] Libro disponible - Ejemplares: {libro.ejemplares_disponibles}")

        # ===============================
        #   PASO 3: Actualizar libro (con failover) - CORREGIDO
        # ===============================
        print("➡ [PASO 3] Actualizando libro en GA...")
        libro.ejemplares_disponibles -= 1
        libro.prestado = True
        fecha_entrega = (datetime.now() + timedelta(weeks=2)).strftime("%Y-%m-%d")

        # ✅ CORREGIDO: Usar el código recibido del GC para la actualización
        actualizar_msg = {
            "codigo": codigo_recibido,
            "data": {
                "ejemplares_disponibles": libro.ejemplares_disponibles,
                "prestado": True,
                "fecha_entrega": fecha_entrega
            }
        }

        print(f"📝 [PASO 3] Datos a actualizar: {actualizar_msg}")
        resp_actualizar = operacion_ga("actualizar", actualizar_msg)

        if resp_actualizar["status"] == "ok":
            msg = f"Préstamo OK: '{libro.titulo}' hasta {fecha_entrega}"
            if ga_actual == GA_REPLICA:
                msg += " [Actualizado en RÉPLICA SECUNDARIA - FAILOVER EXITOSO]"
            print(f"✅ [PASO 3] PRÉSTAMO EXITOSO: {msg}")
            rep_socket.send_json({"status": "ok", "msg": msg})
            print("✅ [MAIN] Respuesta de éxito enviada al GC")
        else:
            error_msg = resp_actualizar.get("msg", "Error al actualizar")
            if ga_actual == GA_REPLICA:
                error_msg += " [Intentado en RÉPLICA SECUNDARIA]"
            print(f"❌ [PASO 3] ERROR en actualización: {error_msg}")
            rep_socket.send_json({"status": "error", "msg": error_msg})
            print("✅ [MAIN] Respuesta de error enviada al GC")

        print("🎉 [MAIN] CICLO DE PRÉSTAMO COMPLETADO EXITOSAMENTE")

    except Exception as e:
        print(f"💥 [MAIN] ERROR INESPERADO en actor préstamo: {e}")
        import traceback
        traceback.print_exc()
        
        error_msg = str(e)
        if ga_actual == GA_REPLICA:
            error_msg += " [En RÉPLICA SECUNDARIA]"
        
        print(f"📤 [MAIN] Enviando error al GC: {error_msg}")
        rep_socket.send_json({"status": "error", "msg": error_msg})
        print("✅ [MAIN] Respuesta de error enviada al GC")