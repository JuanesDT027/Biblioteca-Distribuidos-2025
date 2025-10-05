import zmq
import json

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5555")  # puerto donde corre GC

operaciones = [
    {"operacion": "devolucion", "codigo": "L0010"},
    {"operacion": "renovacion", "codigo": "L0001"},
    {"operacion": "prestamo", "codigo": "L0003"}
]

for op in operaciones:
    print(f">> Enviando {op['operacion']} para {op['codigo']}...")
    socket.send_json(op)
    respuesta = socket.recv_json()
    print("Respuesta del GC:", respuesta)
