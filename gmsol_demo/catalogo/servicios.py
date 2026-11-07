from django.db import transaction

from .models import Venta


class ReglaDeNegocioError(Exception):
    """Se rompió una regla del negocio (ej.: cerrar una orden con deuda)."""


@transaction.atomic
def cerrar_orden(orden):
    if orden.cerrada:
        raise ReglaDeNegocioError("La orden ya está cerrada.")
    if orden.estado == "finalizada":
        raise ReglaDeNegocioError("La orden ya terminó sin venta (no arreglable).")
    if orden.estado == "no_arreglable":
        raise ReglaDeNegocioError("Una orden no arreglable no genera venta: hay que devolver el dinero.")
    if orden.estado != "lista":
        raise ReglaDeNegocioError("Todavía hay equipos pendientes.")
    # El saldo tiene que ser exactamente 0: ni deuda ni pago de más
    if orden.monto_adeudado != 0:
        raise ReglaDeNegocioError("El saldo de la orden debe ser 0 (hay deuda o se pagó de más).")
    return Venta.objects.create(
        orden_trabajo=orden, cliente=orden.cliente, total=orden.total)


@transaction.atomic
def vender_directo(lineas, pagos, cliente=None):
    """Crea una venta directa (sin orden) con sus productos y sus pagos.

    lineas: lista de LineaProductoVenta sin guardar (producto y cantidad_adquirida;
            si no traen precio_vendido se usa el precio de venta del producto).
    pagos:  lista de Pago sin guardar (metodo_pago y monto).
    Si algo falla, no se guarda nada.
    """
    if not lineas:
        raise ReglaDeNegocioError("Una venta necesita al menos un producto.")

    productos = [linea.producto_id for linea in lineas]
    if len(productos) != len(set(productos)):
        raise ReglaDeNegocioError("No repitas el mismo producto: sumá la cantidad en una sola línea.")

    for linea in lineas:
        if linea.precio_vendido is None:
            linea.precio_vendido = linea.producto.precio_venta

    total = sum(linea.subtotal for linea in lineas)
    if sum(pago.monto for pago in pagos) != total:
        raise ReglaDeNegocioError("Los pagos deben sumar exactamente el total de la venta.")

    venta = Venta.objects.create(cliente=cliente, total=total)
    for linea in lineas:
        linea.venta = venta
        linea.full_clean()
        linea.save()
    for pago in pagos:
        pago.venta = venta
        pago.full_clean()
        pago.save()
    return venta