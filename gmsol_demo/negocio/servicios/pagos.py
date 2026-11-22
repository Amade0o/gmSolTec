"""Servicios de dinero: pagos, venta rápida (venta directa) y devoluciones.

Borrar lo cargado por error sigue las reglas del admin: solo en órdenes abiertas, y nunca algo que
deje dinero sin registrar.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ..models import Devolucion, OrdenTrabajo, Pago, Venta
from .comun import ReglaDeNegocioError, exigir_orden_abierta


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

def agregar_pago(orden, metodo, monto, recargo_porcentaje=None):
    """Pago de una orden abierta. Si no se indica el recargo, se copia del método."""
    exigir_orden_abierta(orden)
    pago = Pago(orden_trabajo=orden, metodo_pago=metodo, monto=monto, recargo_porcentaje=recargo_porcentaje)
    pago.full_clean()               # no puede superar lo que falta pagar
    pago.save()
    return pago

def registrar_devolucion(orden, monto=None, linea_reparacion=None, nota=""):
    """Paso 1: registrar que HAY que devolver. El dinero sigue reservado."""
    devolucion = Devolucion(orden_trabajo=orden, monto=monto, linea_reparacion=linea_reparacion, nota=nota)
    devolucion.full_clean()         # orden abierta, no más de lo pagado, reparación válida
    devolucion.save()
    return devolucion


def monto_para_devolver(linea):
    """Cuánto se le devuelve al cliente si se devuelve esta reparación: lo que pagó de más
    una vez que la reparación sale del total, y nunca más que su precio.
    Ej.: pagó $10.000 de una orden de $55.000; si se devuelve una reparación de $15.000
    todavía debe $30.000, así que no hay nada para devolver (es 0)."""
    orden = linea.equipo.orden_trabajo
    cuenta = linea.equipo.estado != "no_arreglable" and linea.id not in orden.lineas_devueltas
    total_sin_la_linea = orden.total - (linea.subtotal if cuenta else 0)
    a_favor = orden.monto_pagado - orden.monto_a_devolver - total_sin_la_linea
    return max(min(linea.precio_vendido, a_favor), Decimal("0.00"))


@transaction.atomic
def devolver_reparacion(linea, metodo=None, nota=""):
    """Devuelve una reparación de la orden: deja de cobrarse (sigue a la vista, marcada como
    devuelta) y se registra la devolución del dinero. Con 'metodo' queda hecha en el acto;
    sin método queda pendiente en Devoluciones."""
    orden = linea.equipo.orden_trabajo
    exigir_orden_abierta(orden)
    if linea.devoluciones.exists():
        raise ReglaDeNegocioError("Esa reparación ya fue devuelta.")
    monto = monto_para_devolver(linea)
    if monto <= 0:
        raise ReglaDeNegocioError(
            f"No hay dinero para devolver por «{linea.reparacion}»: lo que pagó el cliente sigue cubriendo el resto "
            "de la orden. Si esa reparación no se hace, quitala desde la orden.")
    devolucion = registrar_devolucion(orden, monto=monto, linea_reparacion=linea, nota=nota)
    if metodo is not None:
        marcar_devuelta(devolucion, metodo)
    return devolucion


def marcar_devuelta(devolucion, metodo):
    """Paso 2: el dinero YA se devolvió, con este método."""
    if devolucion.devuelta:
        raise ReglaDeNegocioError("Esa devolución ya está hecha.")
    devolucion.metodo_pago = metodo
    devolucion.fecha_devolucion = timezone.now()
    devolucion.full_clean()
    devolucion.save()
    return devolucion

def quitar_pago(pago):
    """Un pago cargado por error (si el cliente se lleva la plata, eso es una devolución)."""
    orden = pago.orden_trabajo
    if orden is None:
        raise ReglaDeNegocioError("Ese pago es de una venta: para sacarlo, anulá la venta.")
    exigir_orden_abierta(orden)
    pagado_sin_este = sum(p.monto for p in orden.pagos.exclude(pk=pago.pk))
    if sum(d.monto for d in orden.devoluciones.all()) > pagado_sin_este:
        raise ReglaDeNegocioError("Hay devoluciones que salen de ese pago: anulá primero la devolución.")
    pago.delete()

def anular_devolucion(devolucion):
    """Una devolución registrada por error, que todavía no se hizo. Si era de una reparación,
    la reparación vuelve a cobrarse."""
    exigir_orden_abierta(devolucion.orden_trabajo)
    if devolucion.devuelta:
        raise ReglaDeNegocioError("Esa devolución ya se hizo (el dinero ya salió): no se puede anular.")
    devolucion.delete()

@transaction.atomic
def anular_venta_directa(venta):
    """Una venta rápida cargada por error: se borra con sus productos y sus pagos."""
    if venta.orden_trabajo_id:
        raise ReglaDeNegocioError("La venta de una orden no se anula: es el cierre de la orden.")
    venta.pagos.all().delete()
    venta.lineas_producto.all().delete()
    venta.delete()

@transaction.atomic
def devolver_saldo_a_favor(orden, metodo):
    """Le devuelve al cliente todo lo que tiene a favor, con 'metodo': marca hechas las devoluciones
    pendientes y, si pagó de más sin devolución registrada, la registra y la marca hecha.
    Devuelve cuánto se devolvió en total."""
    exigir_orden_abierta(orden)
    devuelto = Decimal("0.00")
    for devolucion in orden.devoluciones.filter(fecha_devolucion__isnull=True):
        marcar_devuelta(devolucion, metodo)
        devuelto += devolucion.monto
    orden = OrdenTrabajo.objects.get(pk=orden.pk)       # números al día
    a_favor = -orden.monto_adeudado
    if a_favor > 0:
        marcar_devuelta(registrar_devolucion(orden, monto=a_favor, nota="Saldo a favor del cliente"), metodo)
        devuelto += a_favor
    if devuelto == 0:
        raise ReglaDeNegocioError("No hay dinero para devolverle al cliente.")
    return devuelto
