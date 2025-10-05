import sys 
import os
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import json
import random
from common.LibroUsuario import LibroUsuario

libros = []

# Generar 1000 libros
for i in range(1, 1001):
    titulo = f"Libro {i}"
    autor = f"Autor {random.randint(1, 300)}"
    sede = "SedeA" if i <= 500 else "SedeB"
    total_ejemplares = random.randint(1, 5)

    # 200 libros prestados: 50 en SedeA, 150 en SedeB
    if (i <= 50 and sede == "SedeA") or (i > 850 and sede == "SedeB"):
        prestado = True
        ejemplares_disponibles = max(0, total_ejemplares - 1)
        fecha_entrega = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        renovaciones = [0] + [0]*(total_ejemplares-1)  # el primer ejemplar prestado inicia con 0 renovaciones
    else:
        prestado = False
        ejemplares_disponibles = total_ejemplares
        fecha_entrega = None
        renovaciones = [0]*total_ejemplares

    libro = LibroUsuario(
        codigo=f"L{i:04d}",
        titulo=titulo,
        autor=autor,
        sede=sede,
        ejemplares_disponibles=ejemplares_disponibles,
        prestado=prestado,
        fecha_entrega=fecha_entrega,
        total_ejemplares=total_ejemplares,
        renovaciones=renovaciones
    )
    libros.append(libro.to_dict())

# Guardar en archivo
with open("data/libros.txt", "w", encoding="utf-8") as f:
    for libro in libros:
        f.write(json.dumps(libro) + "\n")

print("✅ Archivo 'libros.txt' creado con 1000 libros (200 prestados) y renovaciones inicializadas.")
