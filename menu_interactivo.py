import zmq
import json
import time
from tabulate import tabulate
from colorama import init, Fore, Style

# Inicializar colorama
init(autoreset=True)

# Configuración ZMQ
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5555")  # puerto del Gestor de Carga

solicitudes = []

# Función para cargar archivo de solicitudes
def cargar_archivo():
    global solicitudes
    archivo = input(Fore.CYAN + "Ingrese el nombre del archivo con solicitudes: " + Style.RESET_ALL)
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            solicitudes = [json.loads(line.strip()) for line in f if line.strip()]
        print(Fore.GREEN + f"✅ {len(solicitudes)} solicitudes cargadas." + Style.RESET_ALL)
    except FileNotFoundError:
        print(Fore.RED + "⚠️ Archivo no encontrado." + Style.RESET_ALL)
    except json.JSONDecodeError as e:
        print(Fore.RED + f"⚠️ Error leyendo archivo: {e}" + Style.RESET_ALL)

# Función para enviar todas las solicitudes cargadas
def enviar_solicitudes():
    if not solicitudes:
        print(Fore.YELLOW + "⚠️ No hay solicitudes cargadas." + Style.RESET_ALL)
        return
    for i, solicitud in enumerate(solicitudes, start=1):
        print(Fore.BLUE + f"[{i}] Enviando {solicitud['operacion']} para {solicitud['codigo']}..." + Style.RESET_ALL)
        socket.send_json(solicitud)
        try:
            respuesta = socket.recv_json()
            print(Fore.GREEN + f"📨 Respuesta del GC: {respuesta}" + Style.RESET_ALL)
        except zmq.ZMQError as e:
            print(Fore.RED + f"⚠️ Error comunicándose con el GC: {e}" + Style.RESET_ALL)
        time.sleep(0.3)

# Función para operación manual con selección mediante tabla
def operacion_manual():
    operaciones = [
        ["1", "Devolucion"],
        ["2", "Renovacion"],
        ["3", "Prestamo"]
    ]
    print(Fore.MAGENTA + "\n=== Seleccione la operación ===" + Style.RESET_ALL)
    print(tabulate(operaciones, headers=["Opción", "Operación"], tablefmt="fancy_grid"))

    while True:
        opcion = input(Fore.YELLOW + "Seleccione el número de la operación: " + Style.RESET_ALL).strip()
        if opcion not in ["1", "2", "3"]:
            print(Fore.RED + f"⚠️ Opción inválida: {opcion}. Intente nuevamente." + Style.RESET_ALL)
            continue
        operacion = operaciones[int(opcion)-1][1].lower()
        break

    while True:
        codigo = input(Fore.CYAN + "Código del libro: " + Style.RESET_ALL).strip()
        if not codigo:
            print(Fore.RED + "⚠️ Código vacío. Intente nuevamente." + Style.RESET_ALL)
            continue
        break

    solicitud = {"operacion": operacion, "codigo": codigo}
    socket.send_json(solicitud)
    try:
        respuesta = socket.recv_json()
        print(Fore.GREEN + f"📨 Respuesta del GC: {respuesta}" + Style.RESET_ALL)
    except zmq.ZMQError as e:
        print(Fore.RED + f"⚠️ Error comunicándose con el GC: {e}" + Style.RESET_ALL)

# Función para mostrar menú principal bonito
def mostrar_menu():
    menu = [
        ["1", "Cargar archivo de solicitudes"],
        ["2", "Enviar todas las solicitudes cargadas"],
        ["3", "Realizar operación manual"],
        ["4", "Salir"]
    ]
    print(Fore.MAGENTA + "\n=== Menú del Proceso Solicitante ===" + Style.RESET_ALL)
    print(tabulate(menu, headers=["Opción", "Descripción"], tablefmt="fancy_grid"))

# Menú principal
def menu_principal():
    while True:
        mostrar_menu()
        opcion = input(Fore.YELLOW + "Seleccione una opción: " + Style.RESET_ALL).strip()
        if opcion == "1":
            cargar_archivo()
        elif opcion == "2":
            enviar_solicitudes()
        elif opcion == "3":
            operacion_manual()
        elif opcion == "4":
            print(Fore.CYAN + "Saliendo..." + Style.RESET_ALL)
            break
        else:
            print(Fore.RED + "⚠️ Opción inválida." + Style.RESET_ALL)

# Ejecutar menú principal
if __name__ == "__main__":
    menu_principal()
