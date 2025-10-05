import zmq
import json
from common.LibroUsuario import LibroUsuario

# Configurar contexto y socket SUB
context = zmq.Context()
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://localhost:5556")  # mismo puerto que PUB del GC
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "Renovacion")

# Cargar BD simulada desde archivo
libros = {}
with open("data/libros.txt", "r") as f:
    for line in f:
        data = json.loads(line)
        libros[data["codigo"]] = LibroUsuario(**data)

print("✅ Actor Renovación iniciado y escuchando...")

while True:
    # Recibir mensaje como string y separar tópico del contenido
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)
    
    # Parsear el JSON del contenido
    data = json.loads(contenido)
    libro_data = data["libro"]
    fecha_nueva = data["fecha_nueva"]
    
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
