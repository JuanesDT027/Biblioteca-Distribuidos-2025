# actores/actor_renovacion.py
import zmq
import json
from datetime import datetime
from common.LibroUsuario import LibroUsuario

context = zmq.Context()
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://localhost:5556")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Renovacion")

# Cargar BD
libros = {}
with open("data/libros.txt", "r") as f:
    for line in f:
        data = json.loads(line)
        libros[data["codigo"]] = LibroUsuario(**data)

print("✅ Actor Renovación iniciado y escuchando...")

while True:
    mensaje_raw = sub_socket.recv_json()
    topico = mensaje_raw.get("topico")
    libro_data = mensaje_raw.get("libro")
    fecha_nueva = mensaje_raw.get("fecha_nueva")
    
    if topico == "Renovacion" and libro_data:
        codigo = libro_data["codigo"]
        libro = libros.get(codigo)
        if libro:
            libro.fecha_entrega = fecha_nueva
            print(f"Libro {libro.titulo} renovado hasta {fecha_nueva}.")
            # Guardar cambios en archivo
            with open("data/libros.txt", "w") as f:
                for l in libros.values():
                    f.write(json.dumps(l.to_dict()) + "\n")
