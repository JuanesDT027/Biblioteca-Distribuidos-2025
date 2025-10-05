import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import json
import random
from common.LibroUsuario import LibroUsuario


# Creamos una lista para los libros
libros = []

# Generar 1000 libros
for i in range(1, 1001):
    titulo = f"Libro {i}"
    autor = f"Autor {random.randint(1, 300)}"
    sede = "SedeA" if i <= 500 else "SedeB"
    ejemplares = random.randint(1, 5)

    # 200 libros prestados: 50 en SedeA, 150 en SedeB
    if (i <= 50 and sede == "SedeA") or (i > 850 and sede == "SedeB"):
        prestado = True
        ejemplares_disponibles = max(0, ejemplares - 1)
    else:
        prestado = False
        ejemplares_disponibles = ejemplares

    libro = LibroUsuario(
        codigo=f"L{i:04d}",
        titulo=titulo,
        autor=autor,
        sede=sede,
        ejemplares_disponibles=ejemplares_disponibles,
        prestado=prestado
    )
    libros.append(libro.to_dict())

# Guardar los libros en un archivo de texto
with open("data/libros.txt", "w") as f:
    for libro in libros:
        f.write(json.dumps(libro) + "\n")

print("✅ Archivo 'libros.txt' creado con 1000 libros (200 prestados).")
