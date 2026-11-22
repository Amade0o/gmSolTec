"""Cómo se escriben los montos en pesos argentinos.

Está acá (y no solo en las pantallas) porque los servicios arman las frases del historial con
montos, y tienen que verse igual que en la pantalla. Los filtros de plantilla de la app web usan
estas mismas funciones.
"""


def numero(valor):
    """42500 -> '42.500'. 1234.5 -> '1.234,50' (formato argentino). Sin signo."""
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return texto[:-3] if texto.endswith(",00") else texto


def pesos(valor):
    """42500 -> '$ 42.500'. Sin signo: quien lo usa dice con palabras si entra o sale."""
    return f"$ {numero(valor)}"
