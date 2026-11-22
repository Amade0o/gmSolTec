"""Órdenes de trabajo: la orden, los equipos que deja el cliente y las reparaciones de cada equipo.

El estado de la orden no se guarda: se calcula a partir de sus equipos, sus pagos y su venta.
"""
from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from .catalogo import ModeloEquipo, Reparacion, TipoEquipo

# Los tipos de equipo (Celular, Notebook, PC…) ya no son una lista fija: están en la tabla
# TipoEquipo y el dueño los agrega desde el Catálogo (pedido del 18/11/2026).

# Estados del equipo dentro de la orden, estos tambien seran estados de la orden
EQUIPO_ORDEN_ESTADO_CHOICES = [
    ('pendiente', 'En revisión / reparación'),
    ('sin_falla', 'Sin falla'),
    ('arreglado', 'Arreglado'),
    ('no_arreglable', 'No arreglable')
]

# Tipos de bloqueo que puede tener un equipo
BLOQUEO_CHOICES = [
    ('pin', 'PIN'),
    ('patron', 'Patrón'),
    ('contrasena', 'Contraseña'),
    ('ninguno', 'Ninguno')
]


class OrdenTrabajo(models.Model):
    cliente = models.ForeignKey("Cliente", on_delete=models.PROTECT, related_name="ordenes")
    fecha_recepcion = models.DateTimeField(auto_now_add=True)

    # El estado de la orden se deriva del estado de sus equipos.
    @property
    def estado(self):
        if self.cerrada:
            return 'cerrada'
        
        equipos = list(self.equipos.all())
        
        if not equipos:
            return 'pendiente'

        if any(equipo.estado == 'pendiente' for equipo in equipos):
            return 'pendiente'

        if all(equipo.estado == 'no_arreglable' for equipo in equipos):
            # Ningún equipo tuvo arreglo, pero se lleva productos: se cobran y se entregan con una venta
            # (caso borde del cable ya entregado; regla del 18/11/2026)
            if self.total > 0:
                return 'lista'
            # Si no queda dinero retenido (nunca hubo seña o ya se devolvió), terminó sin venta
            if self.monto_retenido == 0:
                return 'finalizada'
            return 'no_arreglable'

        return 'lista'  

    @property
    def lineas_devueltas(self):
        """Ids de las reparaciones que tienen una devolución: ya no se cobran."""
        return {d.linea_reparacion_id for d in self.devoluciones.all() if d.linea_reparacion_id}

    @property
    def total(self):
        total = Decimal("0.00")
        devueltas = self.lineas_devueltas

        for equipo in self.equipos.all():
            if equipo.estado == "no_arreglable":
                continue        # lo que no se arregla no se cobra
            for linea in equipo.lineas_reparacion.all():
                if linea.id in devueltas:
                    continue    # reparación devuelta: sigue en la orden, pero no se cobra
                total += linea.subtotal

        for linea in self.lineas_producto.all():
            total += linea.subtotal
            
        return total

    @property
    def monto_devuelto(self):
        # Dinero que ya se le devolvió al cliente
        return sum((d.monto for d in self.devoluciones.all() if d.devuelta), Decimal("0.00"))

    @property
    def monto_a_devolver(self):
        # Dinero que hay que devolver y todavía está reservado
        return sum((d.monto for d in self.devoluciones.all() if not d.devuelta), Decimal("0.00"))

    @property
    def monto_pagado(self):
        # Lo que pagó el cliente menos lo que ya se le devolvió
        total = Decimal("0.00")

        for pago in self.pagos.all():
            total += pago.monto
        return total - self.monto_devuelto

    @property 
    def monto_adeudado(self):
        return self.total - self.monto_pagado

    @property
    def monto_retenido(self):
        if self.cerrada:
            return Decimal("0.00")
        return self.monto_pagado

    @property
    def cerrada(self):
        return hasattr(self, "venta")
    
    @property
    @admin.display(boolean=True, description="¿Adeuda?")
    def adeuda(self):
        return self.monto_adeudado > 0

    def __str__(self):
        return f"Orden #{self.id}"


class EquipoRecibido(models.Model):
    orden_trabajo = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name="equipos")
    tipo = models.ForeignKey(TipoEquipo, to_field="clave", db_column="tipo", on_delete=models.PROTECT,
                             related_name="equipos")
    modelo = models.ForeignKey(ModeloEquipo, on_delete=models.PROTECT, related_name="equipos", blank = True, null = True)
    problema = models.TextField(max_length=500) 
    tipo_bloqueo = models.CharField(max_length=20, choices=BLOQUEO_CHOICES, default='ninguno')
    clave_bloqueo = models.CharField(max_length=100, blank=True)
    accesorios_dejados = models.TextField(max_length=300, blank = True)
    estado = models.CharField(max_length=20, default= 'pendiente', choices=EQUIPO_ORDEN_ESTADO_CHOICES)

    def clean(self):
        super().clean()
        # El resultado (arreglado, sin falla, no arreglable) se carga después de revisar el equipo
        if self.pk is None and self.estado != "pendiente":
            raise ValidationError({"estado": "Un equipo nuevo siempre empieza en revisión: el resultado se carga después."})
        if self.tipo_bloqueo == "ninguno" and self.clave_bloqueo:
            raise ValidationError({"clave_bloqueo": "Si no tiene bloqueo, la clave debe quedar vacía."})

    def __str__(self):
        return f"Equipo #{self.id} | Orden #{self.orden_trabajo.id}"

class LineaReparacion(models.Model):    
    precio_vendido = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    nota = models.TextField(max_length=300, blank=True) #opcional
    equipo = models.ForeignKey(EquipoRecibido, on_delete=models.CASCADE, related_name="lineas_reparacion")
    reparacion = models.ForeignKey(Reparacion, on_delete=models.PROTECT, related_name="lineas")

    @property
    def subtotal(self):
        return self.precio_vendido
    
    def __str__(self):
        return f"{self.reparacion}"
