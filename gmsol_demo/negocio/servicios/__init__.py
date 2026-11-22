"""Reglas del negocio, divididas por tema.

Las pantallas (app web) y el admin no tienen reglas: llaman a estas funciones. Los errores llegan
como ReglaDeNegocioError o como ValidationError (de full_clean).

    comun.py      ReglaDeNegocioError y el control de orden abierta
    ordenes.py    crear, editar, cambiar estados, cerrar y entregar órdenes
    pagos.py      pagos, venta rápida y devoluciones (y anular lo cargado por error)
    clientes.py   clientes y teléfonos

Todo se importa acá, así el resto del código sigue usando `from negocio import servicios`
o `from negocio.servicios import cerrar_orden`.
"""
from .clientes import (
    agregar_telefono, crear_cliente, eliminar_cliente, marcar_telefono_principal, quitar_telefono,
)
from .comun import ReglaDeNegocioError, exigir_orden_abierta
from .ordenes import (
    agregar_equipo, agregar_producto, agregar_reparacion, cambiar_estado_equipo, cerrar_orden,
    crear_orden, eliminar_orden, entregar_orden, quitar_equipo, quitar_producto, quitar_reparacion,
)
from .pagos import (
    agregar_pago, anular_devolucion, anular_venta_directa, devolver_reparacion,
    devolver_saldo_a_favor, marcar_devuelta, monto_para_devolver, quitar_pago, registrar_devolucion,
    vender_directo,
)

__all__ = [
    "ReglaDeNegocioError", "exigir_orden_abierta",
    "agregar_equipo", "agregar_producto", "agregar_reparacion", "cambiar_estado_equipo",
    "cerrar_orden", "crear_orden", "eliminar_orden", "entregar_orden", "quitar_equipo",
    "quitar_producto", "quitar_reparacion",
    "agregar_pago", "anular_devolucion", "anular_venta_directa", "devolver_reparacion",
    "devolver_saldo_a_favor", "marcar_devuelta", "monto_para_devolver", "quitar_pago",
    "registrar_devolucion", "vender_directo",
    "agregar_telefono", "crear_cliente", "eliminar_cliente", "marcar_telefono_principal",
    "quitar_telefono",
]
