"""Servicios de órdenes de trabajo: crear, editar, cambiar el estado de los equipos, cerrar y entregar.

Las pantallas no tienen reglas: llaman a estas funciones. Los errores llegan como
ReglaDeNegocioError o ValidationError (de full_clean).
"""
from django.db import transaction
from django.db.models import ProtectedError

from ..models import EQUIPO_ORDEN_ESTADO_CHOICES, Devolucion, OrdenTrabajo, Venta
from .comun import ReglaDeNegocioError, exigir_orden_abierta
from .pagos import agregar_pago


@transaction.atomic
def cerrar_orden(orden):
    if orden.cerrada:
        raise ReglaDeNegocioError("La orden ya está cerrada.")
    if orden.estado == "no_arreglable":
        raise ReglaDeNegocioError("No tiene arreglo y queda dinero del cliente: primero hay que devolverle el dinero.")
    # "finalizada" (sin arreglo y sin dinero pendiente) también se cierra: se le devuelve el equipo
    # al cliente y queda registrado como entrega sin cargo (venta de $0). Regla del 18/11/2026.
    if orden.estado not in ("lista", "finalizada"):
        raise ReglaDeNegocioError("Todavía hay equipos pendientes.")
    # Si hay una devolución registrada sin hacer, después de cerrar ya no se podría marcar devuelta
    if orden.monto_a_devolver > 0:
        raise ReglaDeNegocioError("Hay dinero para devolver: marcá la devolución como hecha antes de cerrar.")
    # El saldo tiene que ser exactamente 0: ni deuda ni pago de más
    if orden.monto_adeudado != 0:
        raise ReglaDeNegocioError("El saldo de la orden debe ser 0 (hay deuda o se pagó de más).")
    return Venta.objects.create(
        orden_trabajo=orden, cliente=orden.cliente, total=orden.total)

@transaction.atomic
def crear_orden(cliente, equipo, lineas_reparacion, lineas_producto=(), pagos=()):
    """Crea la orden completa con su primer equipo. Si algo falla, no se guarda nada.

    equipo:            EquipoRecibido sin guardar.
    lineas_reparacion: lista de LineaReparacion sin guardar (al menos una).
    lineas_producto:   lista de LineaProductoOrden sin guardar.
    pagos:             lista de Pago sin guardar (la seña), con metodo_pago y monto.
    """
    orden = OrdenTrabajo.objects.create(cliente=cliente)
    agregar_equipo(orden, equipo, lineas_reparacion)
    for linea in lineas_producto:
        agregar_producto(orden, linea)
    for pago in pagos:
        agregar_pago(orden, pago.metodo_pago, pago.monto, pago.recargo_porcentaje)
    return orden


@transaction.atomic
def agregar_equipo(orden, equipo, lineas_reparacion):
    exigir_orden_abierta(orden)
    if not lineas_reparacion:
        raise ReglaDeNegocioError("El equipo necesita al menos una reparación (por ejemplo, Revisión / diagnóstico).")
    equipo.orden_trabajo = orden
    equipo.full_clean()             # un equipo nuevo siempre empieza en revisión
    equipo.save()
    for linea in lineas_reparacion:
        agregar_reparacion(equipo, linea)
    return equipo


def agregar_reparacion(equipo, linea):
    exigir_orden_abierta(equipo.orden_trabajo)
    if linea.reparacion.es_revision and any(l.reparacion.es_revision for l in equipo.lineas_reparacion.all()):
        raise ReglaDeNegocioError("«Revisión / diagnóstico» va una sola vez por equipo, y este ya la tiene.")
    linea.equipo = equipo
    linea.full_clean()
    linea.save()
    return linea


def quitar_reparacion(linea):
    equipo = linea.equipo
    exigir_orden_abierta(equipo.orden_trabajo)
    if equipo.lineas_reparacion.count() <= 1:
        raise ReglaDeNegocioError("El equipo tiene que quedar con al menos una reparación.")
    try:
        linea.delete()
    except ProtectedError:
        raise ReglaDeNegocioError("Esa reparación tiene una devolución registrada: no se puede quitar.")


def agregar_producto(orden, linea):
    exigir_orden_abierta(orden)
    if orden.lineas_producto.filter(producto_id=linea.producto_id).exists():
        raise ReglaDeNegocioError("Ese producto ya está en la orden: cambiá la cantidad en vez de repetirlo.")
    linea.orden_trabajo = orden
    linea.full_clean()
    linea.save()
    return linea


def quitar_producto(linea):
    exigir_orden_abierta(linea.orden_trabajo)
    linea.delete()

def cambiar_estado_equipo(equipo, estado):
    exigir_orden_abierta(equipo.orden_trabajo)
    if estado not in dict(EQUIPO_ORDEN_ESTADO_CHOICES):
        raise ReglaDeNegocioError("Estado de equipo desconocido.")
    equipo.estado = estado
    equipo.full_clean()
    equipo.save()
    return equipo

@transaction.atomic
def entregar_orden(orden, metodo=None, recargo_porcentaje=None):
    """Retiro del equipo: si debe algo, cobra el saldo con 'metodo' y cierra la orden con su Venta.
    Si algo falla (por ejemplo, la orden no está lista), no se guarda ni el pago."""
    if orden.monto_adeudado > 0:
        if metodo is None:
            raise ReglaDeNegocioError("Elegí con qué método paga el saldo.")
        agregar_pago(orden, metodo, orden.monto_adeudado, recargo_porcentaje)
    return cerrar_orden(orden)

def quitar_equipo(equipo):
    orden = equipo.orden_trabajo
    exigir_orden_abierta(orden)
    if orden.equipos.count() <= 1:
        raise ReglaDeNegocioError("La orden tiene que quedar con al menos un equipo. Si no va, eliminá la orden entera.")
    if Devolucion.objects.filter(linea_reparacion__equipo=equipo).exists():
        raise ReglaDeNegocioError("Ese equipo tiene una reparación devuelta: no se puede quitar.")
    equipo.delete()             # sus reparaciones se borran con él

def eliminar_orden(orden):
    """Una orden cargada por error. Si tiene pagos o devoluciones, primero se quitan: así no se
    pierde dinero registrado."""
    exigir_orden_abierta(orden)
    if orden.pagos.exists() or orden.devoluciones.exists():
        raise ReglaDeNegocioError("La orden tiene pagos o devoluciones: quitalos primero (así no se pierde plata registrada).")
    orden.delete()              # equipos, reparaciones y productos se borran con ella
