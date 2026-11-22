"""Lo que comparten todos los servicios: el error de regla de negocio y el control de orden abierta."""


class ReglaDeNegocioError(Exception):
    """Se rompió una regla del negocio (ej.: cerrar una orden con deuda)."""


def exigir_orden_abierta(orden):
    """Una orden cerrada (con su venta) no se toca."""
    if orden.cerrada:
        raise ReglaDeNegocioError("La orden ya está cerrada: no se puede modificar.")
