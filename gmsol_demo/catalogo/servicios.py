from decimal import Decimal

from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone

from .models import EQUIPO_ORDEN_ESTADO_CHOICES, Devolucion, OrdenTrabajo, Pago, Telefono, Venta


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
    # Si hay una devolución registrada sin hacer, después de cerrar ya no se podría marcar devuelta
    if orden.monto_a_devolver > 0:
        raise ReglaDeNegocioError("Hay dinero para devolver: marcá la devolución como hecha antes de cerrar.")
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


# ---------- Servicios de la interfaz propia (etapa 7) ----------
# Las pantallas no tienen reglas: llaman a estas funciones.
# Los errores llegan como ReglaDeNegocioError o ValidationError (de full_clean).

def _orden_abierta(orden):
    if orden.cerrada:
        raise ReglaDeNegocioError("La orden ya está cerrada: no se puede modificar.")


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
    _orden_abierta(orden)
    if not lineas_reparacion:
        raise ReglaDeNegocioError("El equipo necesita al menos una reparación (por ejemplo, Revisión / diagnóstico).")
    equipo.orden_trabajo = orden
    equipo.full_clean()             # un equipo nuevo siempre empieza en revisión
    equipo.save()
    for linea in lineas_reparacion:
        agregar_reparacion(equipo, linea)
    return equipo


def agregar_reparacion(equipo, linea):
    _orden_abierta(equipo.orden_trabajo)
    linea.equipo = equipo
    linea.full_clean()
    linea.save()
    return linea


def quitar_reparacion(linea):
    equipo = linea.equipo
    _orden_abierta(equipo.orden_trabajo)
    if equipo.lineas_reparacion.count() <= 1:
        raise ReglaDeNegocioError("El equipo tiene que quedar con al menos una reparación.")
    try:
        linea.delete()
    except ProtectedError:
        raise ReglaDeNegocioError("Esa reparación tiene una devolución registrada: no se puede quitar.")


def agregar_producto(orden, linea):
    _orden_abierta(orden)
    if orden.lineas_producto.filter(producto_id=linea.producto_id).exists():
        raise ReglaDeNegocioError("Ese producto ya está en la orden: cambiá la cantidad en vez de repetirlo.")
    linea.orden_trabajo = orden
    linea.full_clean()
    linea.save()
    return linea


def quitar_producto(linea):
    _orden_abierta(linea.orden_trabajo)
    linea.delete()


def agregar_pago(orden, metodo, monto, recargo_porcentaje=None):
    """Pago de una orden abierta. Si no se indica el recargo, se copia del método."""
    _orden_abierta(orden)
    pago = Pago(orden_trabajo=orden, metodo_pago=metodo, monto=monto, recargo_porcentaje=recargo_porcentaje)
    pago.full_clean()               # no puede superar lo que falta pagar
    pago.save()
    return pago


def cambiar_estado_equipo(equipo, estado):
    _orden_abierta(equipo.orden_trabajo)
    if estado not in dict(EQUIPO_ORDEN_ESTADO_CHOICES):
        raise ReglaDeNegocioError("Estado de equipo desconocido.")
    equipo.estado = estado
    equipo.full_clean()
    equipo.save()
    return equipo


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
    _orden_abierta(orden)
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


@transaction.atomic
def entregar_orden(orden, metodo=None, recargo_porcentaje=None):
    """Retiro del equipo: si debe algo, cobra el saldo con 'metodo' y cierra la orden con su Venta.
    Si algo falla (por ejemplo, la orden no está lista), no se guarda ni el pago."""
    if orden.monto_adeudado > 0:
        if metodo is None:
            raise ReglaDeNegocioError("Elegí con qué método paga el saldo.")
        agregar_pago(orden, metodo, orden.monto_adeudado, recargo_porcentaje)
    return cerrar_orden(orden)


# ---------- Clientes y teléfonos ----------
# Regla: un cliente con teléfonos tiene exactamente uno principal.

@transaction.atomic
def crear_cliente(cliente, telefono=""):
    """Guarda un Cliente nuevo (sin guardar) y, si viene, su teléfono como principal."""
    cliente.full_clean()
    cliente.save()
    if telefono:
        agregar_telefono(cliente, telefono)
    return cliente


@transaction.atomic
def agregar_telefono(cliente, numero, principal=False):
    """El primer teléfono del cliente queda como principal."""
    numero = (numero or "").strip()
    if not numero:
        raise ReglaDeNegocioError("Escribí el número de teléfono.")
    if cliente.telefonos.filter(numero=numero).exists():
        raise ReglaDeNegocioError("Ese teléfono ya está cargado.")
    principal = principal or not cliente.telefonos.exists()
    if principal:
        cliente.telefonos.update(principal=False)
    telefono = Telefono(cliente=cliente, numero=numero, principal=principal)
    telefono.full_clean()
    telefono.save()
    return telefono


@transaction.atomic
def marcar_telefono_principal(telefono):
    telefono.cliente.telefonos.exclude(pk=telefono.pk).update(principal=False)
    telefono.principal = True
    telefono.save(update_fields=["principal"])
    return telefono


@transaction.atomic
def quitar_telefono(telefono):
    """Si se quita el principal, el que queda más antiguo pasa a ser principal."""
    cliente, era_principal = telefono.cliente, telefono.principal
    telefono.delete()
    if era_principal:
        siguiente = cliente.telefonos.order_by("id").first()
        if siguiente:
            marcar_telefono_principal(siguiente)
