# actores/actor_devolucion.py
import zmq
import json
from common.LibroUsuario import LibroUsuario

# Configurar socket SUB
context = zmq.Context()
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://localhost:5556")  # mismo puerto que PUB del GC
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Devolucion")

# Cargar BD simulada desde archivo
libros = {}
with open("data/libros.txt", "r") as f:
    for line in f:
        data = json.loads(line)
        libros[data["codigo"]] = LibroUsuario(**data)

print("✅ Actor Devolución iniciado y escuchando...")

while True:
    mensaje_raw = sub_socket.recv_json()
    topico = mensaje_raw.get("topico")
    libro_data = mensaje_raw.get("libro")
    
    if topico == "Devolucion" and libro_data:
        codigo = libro_data["codigo"]
        libro = libros.get(codigo)
        if libro:
            libro.prestado = False
            libro.ejemplares_disponibles += 1
            print(f"Libro {libro.titulo} actualizado como disponible.")
            # Guardar cambios en archivo
            with open("data/libros.txt", "w") as f:
                for l in libros.values():
                    f.write(json.dumps(l.to_dict()) + "\n")
