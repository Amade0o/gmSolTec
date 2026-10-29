from django.db import transaction

from .models import Venta


class ReglaDeNegocioError(Exception):
    """Se rompió una regla del negocio (ej.: cerrar una orden con deuda)."""


@transaction.atomic
def cerrar_orden(orden):
    if orden.cerrada:
        raise ReglaDeNegocioError("La orden ya está cerrada.")
    if orden.estado == "no_arreglable":
        raise ReglaDeNegocioError("Una orden no arreglable no genera venta: se devuelve el dinero.")
    if orden.estado != "lista":
        raise ReglaDeNegocioError("Todavía hay equipos pendientes.")
    if orden.adeuda:
        raise ReglaDeNegocioError("La orden tiene saldo pendiente.")
    return Venta.objects.create(
        orden_trabajo=orden, cliente=orden.cliente, total=orden.total)