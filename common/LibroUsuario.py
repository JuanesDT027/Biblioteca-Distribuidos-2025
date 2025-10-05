class LibroUsuario:
    def __init__(self, codigo, titulo, autor, sede, ejemplares_disponibles, prestado, fecha_entrega=None, total_ejemplares=1, renovaciones=None):
        self.codigo = codigo
        self.titulo = titulo
        self.autor = autor
        self.sede = sede
        self.ejemplares_disponibles = ejemplares_disponibles
        self.prestado = prestado
        self.fecha_entrega = fecha_entrega
        self.total_ejemplares = total_ejemplares
        self.renovaciones = renovaciones if renovaciones is not None else [0]*total_ejemplares

    def to_dict(self):
        return {
            "codigo": self.codigo,
            "titulo": self.titulo,
            "autor": self.autor,
            "sede": self.sede,
            "ejemplares_disponibles": self.ejemplares_disponibles,
            "prestado": self.prestado,
            "fecha_entrega": self.fecha_entrega,
            "total_ejemplares": self.total_ejemplares,
            "renovaciones": self.renovaciones
        }
