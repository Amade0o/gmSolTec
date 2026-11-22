"""Modelos del negocio, divididos por tema.

Cada clase hereda de models.Model. En models va cada clase que representa una tabla de la base
de datos: Django convierte cada clase en una tabla y cada atributo en una columna.

    catalogo.py   lo que se vende y se repara (productos, marcas, modelos, reparaciones)
    clientes.py   clientes y teléfonos
    ordenes.py    órdenes de trabajo, equipos recibidos y líneas de reparación
    ventas.py     métodos de pago, pagos, devoluciones, ventas y líneas de producto
    caja.py       cajas (efectivo, digital, señas) y sus movimientos
    historial.py  el historial de cambios, en frases

Todo se importa acá, así el resto del código sigue usando `from negocio.models import Pago`
sin saber en qué archivo está cada clase.
"""
from .caja import (
    CAJA_CHOICES, CAJAS_PRINCIPALES, CAJAS_SENAS, SIGNO_DEL_TIPO, TIPO_MOVIMIENTO_CHOICES, MovimientoCaja,
)
from .catalogo import (
    CategoriaProducto, CategoriaReparacion, Marca, ModeloEquipo, Producto, Reparacion, TipoEquipo,
)
from .clientes import Cliente, Telefono
from .historial import ACCION_CHOICES, AREA_CHOICES, Cambio
from .ordenes import (
    BLOQUEO_CHOICES, EQUIPO_ORDEN_ESTADO_CHOICES, EquipoRecibido, LineaReparacion, OrdenTrabajo,
)
from .ventas import (
    CUENTA_CHOICES, Devolucion, LineaProductoAbstracta, LineaProductoOrden, LineaProductoVenta,
    MetodoPago, Pago, Venta,
)

__all__ = [
    "CategoriaProducto", "CategoriaReparacion", "Marca", "ModeloEquipo", "Producto", "Reparacion",
    "TipoEquipo",
    "Cliente", "Telefono",
    "BLOQUEO_CHOICES", "EQUIPO_ORDEN_ESTADO_CHOICES", "EquipoRecibido", "LineaReparacion",
    "OrdenTrabajo",
    "CUENTA_CHOICES", "Devolucion", "LineaProductoAbstracta", "LineaProductoOrden",
    "LineaProductoVenta", "MetodoPago", "Pago", "Venta",
    "CAJA_CHOICES", "CAJAS_PRINCIPALES", "CAJAS_SENAS", "SIGNO_DEL_TIPO", "TIPO_MOVIMIENTO_CHOICES",
    "MovimientoCaja",
    "ACCION_CHOICES", "AREA_CHOICES", "Cambio",
]
