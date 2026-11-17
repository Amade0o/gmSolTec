"""Filtros de plantilla: pesos argentinos, saldo en palabras, estados y pista de progreso."""
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
    if _sin_precio(orden):
        return "Sin precio todavía"
    return saldo_monto(orden.monto_adeudado)


def _sin_precio(orden):
    """Orden abierta sin nada cobrable ni pagado (ej.: solo la revisión a $0): no está "saldada"."""
    return not orden.cerrada and orden.total == 0 and orden.monto_pagado == 0 and orden.estado == "pendiente"


@register.filter
def saldo_clase(orden):
    """Color del recuadro del saldo: debe / a favor / ok / sin precio."""
    if _sin_precio(orden):
        return "neutro"
    if orden.monto_adeudado > 0:
        return "debe"
    return "afavor" if orden.monto_adeudado < 0 else "ok"


# Texto del botón "+ Nuevo" según el desplegable (ver forms.con_alta_rapida)
NUEVO = {"categorias-producto": "Nueva categoría", "marcas": "Nueva marca", "modelos": "Nuevo modelo",
         "categorias-reparacion": "Nueva categoría", "reparaciones": "Nueva reparación"}


@register.filter
def alta_rapida(campo):
    """(sección, texto) si el desplegable admite "+ Nuevo"; si no, None."""
    seccion = campo.field.widget.attrs.get("data-catalogo")
    return (seccion, NUEVO[seccion]) if seccion in NUEVO else None


@register.filter
def saldo_monto(pendiente):
    """El saldo en palabras: los números negativos nunca se muestran solos."""
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


# Estado de cada equipo: (texto, clase de color)
ESTADOS_EQUIPO = {
    "pendiente": ("En revisión / reparación", "wip"),
    "arreglado": ("Arreglado", "ok"),
    "sin_falla": ("Sin falla", "ok"),
    "no_arreglable": ("No arreglable", "bad"),
}


@register.filter
def estado_equipo_clase(equipo):
    return ESTADOS_EQUIPO[equipo.estado][1]


@register.filter
def telefono_principal(cliente):
    """El teléfono principal (o el primero, si ninguno está marcado). Usa los teléfonos ya traídos."""
    telefonos = list(cliente.telefonos.all())
    for t in telefonos:
        if t.principal:
            return t.numero
    return telefonos[0].numero if telefonos else ""


@register.filter
def venta_texto(venta):
    """Qué se vendió, en pocas palabras."""
    if venta.orden_trabajo_id:
        return f"Orden #{venta.orden_trabajo_id} · {equipos_texto(venta.orden_trabajo)}"
    lineas = list(venta.lineas_producto.all())
    if not lineas:
        return "-"
    primera = f"{lineas[0].cantidad_adquirida}× {lineas[0].producto}"
    return primera if len(lineas) == 1 else f"{primera} + {len(lineas) - 1} más"
