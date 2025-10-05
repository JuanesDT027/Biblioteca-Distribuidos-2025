# common/LibroUsuario.py

class LibroUsuario:
    def __init__(self, codigo, titulo, autor, sede, ejemplares_disponibles, prestado):
        self.codigo = codigo
        self.titulo = titulo
        self.autor = autor
        self.sede = sede
        self.ejemplares_disponibles = ejemplares_disponibles
        self.prestado = prestado

    def to_dict(self):
        return {
            "codigo": self.codigo,
            "titulo": self.titulo,
            "autor": self.autor,
            "sede": self.sede,
            "ejemplares_disponibles": self.ejemplares_disponibles,
            "prestado": self.prestado
        }
