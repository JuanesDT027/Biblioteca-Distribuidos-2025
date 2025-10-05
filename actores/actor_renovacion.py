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
with open("data/libros.txt", "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        libros[data["codigo"]] = LibroUsuario(**data)

print("✅ Actor Renovación iniciado y escuchando...")

MAX_RENOVACIONES = 2  # máximo permitido por ejemplar

while True:
    mensaje_raw = sub_socket.recv_string()
    topico, contenido = mensaje_raw.split(" ", 1)

    data = json.loads(contenido)
    libro_data = data.get("libro")
    fecha_nueva = data.get("fecha_nueva")

    if topico == "Renovacion" and libro_data:
        codigo = libro_data["codigo"]
        libro = libros.get(codigo)
        if libro:
            # Encontrar el primer ejemplar prestado para renovar
            ejemplar_index = None
            for i in range(libro.total_ejemplares):
                if libro.renovaciones[i] < MAX_RENOVACIONES:
                    ejemplar_index = i
                    break

            if ejemplar_index is not None:
                # Incrementar renovaciones y actualizar fecha
                libro.renovaciones[ejemplar_index] += 1
                libro.fecha_entrega = fecha_nueva
                print(f"Libro {libro.titulo} ejemplar {ejemplar_index+1} renovado hasta {fecha_nueva} "
                      f"(Renovaciones: {libro.renovaciones[ejemplar_index]}/{MAX_RENOVACIONES})")
            else:
                print(f"⚠️ No se puede renovar {libro.titulo}: todos los ejemplares alcanzaron el límite de {MAX_RENOVACIONES} renovaciones.")

            # Guardar cambios en archivo
            with open("data/libros.txt", "w", encoding="utf-8") as f:
                for l in libros.values():
                    f.write(json.dumps(l.to_dict()) + "\n")
