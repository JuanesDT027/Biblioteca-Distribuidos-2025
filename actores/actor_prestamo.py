import zmq
import json
from common.LibroUsuario import LibroUsuario

# Contexto ZMQ
context = zmq.Context()

# Socket REP para atender solicitudes del Gestor de Carga
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://*:5557")  # puerto exclusivo para préstamos

# Cargar BD simulada desde archivo
libros = {}
with open("data/libros.txt", "r") as f:
    for line in f:
        data = json.loads(line)
        libros[data["codigo"]] = LibroUsuario(**data)

print("✅ Actor Préstamo iniciado y escuchando...")

while True:
    # Recibir solicitud de préstamo
    mensaje = rep_socket.recv_json()
    codigo = mensaje.get("codigo")
    libro = libros.get(codigo)
    
    if libro and libro.ejemplares_disponibles > 0:
        libro.ejemplares_disponibles -= 1
        libro.prestado = True
        rep_socket.send_json({"status": "ok", "msg": f"Préstamo autorizado para {libro.titulo}"})
        print(f"Préstamo autorizado para {libro.titulo}.")
    else:
        rep_socket.send_json({"status": "error", "msg": f"Préstamo DENEGADO para código {codigo}"})
        print(f"Préstamo DENEGADO para código {codigo}.")

    # Guardar cambios en archivo
    with open("data/libros.txt", "w") as f:
        for l in libros.values():
            f.write(json.dumps(l.to_dict()) + "\n")
