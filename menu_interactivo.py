# ps_interactivo.py
import zmq
import json
import time

# Configuración ZMQ
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5555")  # puerto del GC

solicitudes = []

def cargar_archivo():
    global solicitudes
    archivo = input("Ingrese el nombre del archivo con solicitudes: ")
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            solicitudes = [json.loads(line.strip()) for line in f if line.strip()]
        print(f"✅ {len(solicitudes)} solicitudes cargadas.")
    except FileNotFoundError:
        print("⚠️ Archivo no encontrado.")
    except json.JSONDecodeError as e:
        print(f"⚠️ Error leyendo archivo: {e}")

def enviar_solicitudes():
    if not solicitudes:
        print("⚠️ No hay solicitudes cargadas.")
        return
    for i, solicitud in enumerate(solicitudes, start=1):
        print(f"[{i}] Enviando {solicitud['operacion']} para {solicitud['codigo']}...")
        socket.send_json(solicitud)
        respuesta = socket.recv_json()
        print("Respuesta del GC:", respuesta)
        time.sleep(0.3)  # opcional

def operacion_manual():
    operacion = input("Tipo de operación (devolucion/renovacion/prestamo): ").strip()
    codigo = input("Código del libro: ").strip()
    solicitud = {"operacion": operacion, "codigo": codigo}
    socket.send_json(solicitud)
    respuesta = socket.recv_json()
    print("Respuesta del GC:", respuesta)

# Menú principal
while True:
    print("\n=== Menú del Proceso Solicitante ===")
    print("1. Cargar archivo de solicitudes")
    print("2. Enviar todas las solicitudes cargadas")
    print("3. Realizar operación manual")
    print("4. Salir")
    opcion = input("Seleccione una opción: ").strip()

    if opcion == "1":
        cargar_archivo()
    elif opcion == "2":
        enviar_solicitudes()
    elif opcion == "3":
        operacion_manual()
    elif opcion == "4":
        print("Saliendo...")
        break
    else:
        print("⚠️ Opción inválida.")

if __name__ == "__main__":
        menu_principal()
