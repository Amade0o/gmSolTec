from django import template

register = template.Library()


def _numero(valor):
    """42500 -> '42.500'. 1234.5 -> '1.234,50' (formato argentino)."""
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return texto[:-3] if texto.endswith(",00") else texto


@register.filter
def pesos(valor):
    return f"$ {_numero(valor)}"


@register.filter
def saldo(orden):
    pendiente = orden.monto_adeudado
    if pendiente > 0:
        return f"Debe {pesos(pendiente)}"
    if pendiente < 0:
        return f"A favor: {pesos(pendiente)} (devolver)"
    return "Saldado"


ESTADOS = {
    "pendiente": ("En revisión / reparación", "wip"),
    "lista": ("Lista", "ok"),
    "no_arreglable": ("No arreglable", "bad"),
    "finalizada": ("Finalizada", "ok"),
    "cerrada": ("Cerrada", "ok"),
}


@register.filter
def estado_texto(orden):
    return ESTADOS[orden.estado][0]


@register.filter
def estado_clase(orden):
    return ESTADOS[orden.estado][1]


# Pista de progreso: Recibida · Revisión · Lista · Entregada.
# Para cada estado de la orden, en qué paso está (empieza en 0).
PASO_ACTUAL = {
    "pendiente": 1,
    "lista": 2,
    "no_arreglable": 2,     # se revisó y terminó ahí (en rojo)
    "finalizada": 2,
    "cerrada": 3,
}


@register.filter
def pista(orden):
    """Devuelve los 4 pasos: 'hecho', 'actual' o '' (todavía no llegó)."""
    actual = PASO_ACTUAL[orden.estado]
    pasos = []
    for i in range(4):
        if i < actual:
            pasos.append("hecho")
        elif i == actual:
            pasos.append("actual")
        else:
            pasos.append("")
    return pasos


@register.filter
def equipos_texto(orden):
    nombres = [e.modelo.nombre if e.modelo else e.get_tipo_display() for e in orden.equipos.all()]
    if not nombres:
        return "-"
    return nombres[0] if len(nombres) == 1 else f"{nombres[0]} + {len(nombres) - 1} más"