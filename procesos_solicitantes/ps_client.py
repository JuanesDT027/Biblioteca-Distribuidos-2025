import zmq
import time
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

from LibroUsuario import LibroUsuario


context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5555")  # Usa localhost si estás probando en tu PC

def devolverLibro():
    libro = LibroUsuario("001", "El Principito", "Antoine de Saint-Exupéry", "Bogotá")
    mensaje = {"operacion": "devolver", "libro_usuario": libro.to_dict(), "timestamp": time.time()}
    socket.send_json(mensaje)
    print("[PS] Enviando devolución...")
    respuesta = socket.recv_json()
    print("[PS] Respuesta del Gestor:", respuesta)

def renovarLibro():
    libro = LibroUsuario("002", "Cien años de soledad", "Gabriel García Márquez", "Cali")
    mensaje = {"operacion": "renovar", "libro_usuario": libro.to_dict(), "timestamp": time.time()}
    socket.send_json(mensaje)
    print("[PS] Enviando renovación...")
    respuesta = socket.recv_json()
    print("[PS] Respuesta del Gestor:", respuesta)

def solicitarPrestamo():
    libro = LibroUsuario("003", "1984", "George Orwell", "Medellín")
    mensaje = {"operacion": "solicitar", "libro_usuario": libro.to_dict(), "timestamp": time.time()}
    socket.send_json(mensaje)
    print("[PS] Enviando solicitud de préstamo...")
    respuesta = socket.recv_json()
    print("[PS] Respuesta del Gestor:", respuesta)

# Prueba todas las operaciones
devolverLibro()
time.sleep(1)
renovarLibro()
time.sleep(1)
solicitarPrestamo()
