class LibroUsuario:
    def __init__(self, codigo, titulo, autor, sede):
        self.codigo = codigo
        self.titulo = titulo
        self.autor = autor
        self.sede = sede

    def to_dict(self):
        return {
            "codigo": self.codigo,
            "titulo": self.titulo,
            "autor": self.autor,
            "sede": self.sede
        }
