"""Dinero y ventas: métodos de pago, pagos, devoluciones, ventas y sus líneas de producto."""
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .catalogo import Producto
from .clientes import Cliente
from .ordenes import OrdenTrabajo

# Tipos de pago que puede tener una orden de trabajo
CUENTA_CHOICES = [
    ('efectivo', 'Efectivo'),
    ('digital', 'Digital')
]


class MetodoPago(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    cuenta = models.CharField(max_length=20, choices=CUENTA_CHOICES)
    recargo_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default = 0,validators=[MinValueValidator(0)])
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} | {self.cuenta} | {self.recargo_porcentaje}%"

class Pago(models.Model):
    orden_trabajo = models.ForeignKey(OrdenTrabajo, on_delete=models.PROTECT,related_name="pagos", null = True, blank = True) #null y blank son para que no sea obligatorio, ya que un pago puede ser de una venta directa
    metodo_pago = models.ForeignKey(MetodoPago, on_delete=models.PROTECT, related_name="pagos")
    venta = models.ForeignKey("Venta", on_delete=models.PROTECT, null=True, blank=True, related_name="pagos")
    monto = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    recargo_porcentaje = models.DecimalField(max_digits= 5, decimal_places=2, blank=True, validators=[MinValueValidator(0)])
    fecha = models.DateTimeField(auto_now_add=True)

    #Esto es para que el Pago no pueda ser de una venta y de una orden de trabajo a la vez
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(orden_trabajo__isnull=False, venta__isnull=True)
                           | models.Q(orden_trabajo__isnull=True, venta__isnull=False)),
                name="pago_orden_o_venta",
            )
        ]

    @property
    def recargo_monto(self):
        if self.monto is None or self.recargo_porcentaje is None:
            return Decimal("0.00")
        
        # Se redondea a centavos (los montos reales no tienen fracciones de centavo)
        return (self.monto * self.recargo_porcentaje / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
 
    @property
    def total_cobrado(self):
        if self.monto is None:
            return Decimal("0.00")
    
        return self.monto + self.recargo_monto

    @property
    def retenido(self):
        if self.orden_trabajo_id is None:   # pago de venta directa
            return False
        return not self.orden_trabajo.cerrada

    def clean(self):
        super().clean()
        if self.orden_trabajo_id and self.venta_id:
            raise ValidationError("El pago pertenece a una orden o a una venta, no a las dos.")
        # El pago no puede superar lo que falta pagar.
        # Si la orden todavía no tiene precio (total 0), se permite la seña.
        if self.orden_trabajo_id and self.monto is not None:
            # Un pago ya guardado que no cambió no se vuelve a controlar: el total de la
            # orden pudo bajar después (ej.: un equipo no arreglable) y el pago sigue siendo válido.
            anterior = Pago.objects.filter(pk=self.pk).values_list("monto", flat=True).first() if self.pk else None
            if anterior != self.monto:
                orden = self.orden_trabajo
                if orden.total > 0:
                    otros_pagos = sum(p.monto for p in orden.pagos.exclude(pk=self.pk)) - orden.monto_devuelto
                    if self.monto > orden.total - otros_pagos:
                        raise ValidationError("El pago supera lo que falta pagar de la orden.")

    def save(self, *args, **kwargs):
        if self.recargo_porcentaje is None:      # vacío → copia el del método
            self.recargo_porcentaje = self.metodo_pago.recargo_porcentaje
        super().save(*args, **kwargs)

    def __str__(self):
        if self.orden_trabajo_id:
            dueno = f"Orden #{self.orden_trabajo_id}"
        elif self.venta_id:
            dueno = f"Venta #{self.venta_id}"
        else:
            dueno = "Sin asignar"
        return f"Pago #{self.id} | {dueno} | Monto: ${self.monto} | Total cobrado: ${self.total_cobrado}"


class Devolucion(models.Model):
    orden_trabajo = models.ForeignKey(OrdenTrabajo, on_delete=models.PROTECT, related_name="devoluciones")
    # Opcional: devolver una reparación completa (el monto se completa solo)
    linea_reparacion = models.ForeignKey("LineaReparacion", on_delete=models.PROTECT, null=True, blank=True, related_name="devoluciones")
    # Si hay una reparación elegida y se deja vacío, se completa con su precio
    monto = models.DecimalField(max_digits=10, decimal_places=2, blank=True, validators=[MinValueValidator(Decimal("0.01"))])
    nota = models.TextField(max_length=300, blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    # Se completan cuando se devuelve el dinero (la fecha se pone sola al elegir el método)
    metodo_pago = models.ForeignKey(MetodoPago, on_delete=models.PROTECT, null=True, blank=True, related_name="devoluciones")
    # Vacía = hay que devolver el dinero (está reservado). Con fecha = ya se devolvió
    fecha_devolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "devoluciones"

    @property
    def devuelta(self):
        return self.fecha_devolucion is not None

    def clean(self):
        super().clean()
        # Una devolución ya hecha no se modifica: el dinero ya salió
        if self.pk:
            anterior = Devolucion.objects.filter(pk=self.pk).first()
            if anterior and anterior.devuelta and (
                    anterior.monto != self.monto or anterior.linea_reparacion_id != self.linea_reparacion_id):
                raise ValidationError("Esta devolución ya se hizo: no se puede modificar.")
        if self.linea_reparacion_id:
            linea = self.linea_reparacion
            if self.orden_trabajo_id and linea.equipo.orden_trabajo_id != self.orden_trabajo_id:
                raise ValidationError({"linea_reparacion": "Esa reparación no es de esta orden."})
            # Cualquier reparación de la orden se puede devolver (un equipo no arreglable, o una
            # reparación que se cancela). Al devolverla deja de sumar al total. Una sola vez.
            if linea.devoluciones.exclude(pk=self.pk).exists():
                raise ValidationError({"linea_reparacion": "Esa reparación ya tiene una devolución."})
            if self.monto is None:
                self.monto = linea.precio_vendido
        if self.monto is None:
            raise ValidationError("Indicá el monto o elegí la reparación a devolver.")
        if self.monto <= 0:
            raise ValidationError({"monto": "El monto a devolver debe ser mayor a 0."})
        if self.fecha_devolucion and not self.metodo_pago_id:
            raise ValidationError({"metodo_pago": "Indicá con qué método se devolvió el dinero."})
        if self.orden_trabajo_id:
            orden = self.orden_trabajo
            if orden.cerrada:
                raise ValidationError("La orden ya se cerró con una venta.")
            # Entre todas las devoluciones (pendientes y hechas) no pueden superar lo pagado
            pagado = sum(p.monto for p in orden.pagos.all())
            otras = sum(d.monto for d in orden.devoluciones.exclude(pk=self.pk))
            if self.monto > pagado - otras:
                raise ValidationError("La devolución supera lo que pagó el cliente.")

    def save(self, *args, **kwargs):
        if self.monto is None and self.linea_reparacion_id:
            self.monto = self.linea_reparacion.precio_vendido
        if self.metodo_pago_id and not self.fecha_devolucion:
            self.fecha_devolucion = timezone.now()      # elegir el método = ya se devolvió
        super().save(*args, **kwargs)

    def __str__(self):
        estado = "devuelta" if self.devuelta else "falta devolver"
        return f"Devolución #{self.id} | Orden #{self.orden_trabajo_id} | ${self.monto} | {estado}"


class Venta(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    cliente = models.ForeignKey(Cliente, on_delete= models.PROTECT, null = True, blank = True, related_name = "ventas_cliente")
    orden_trabajo = models.OneToOneField(OrdenTrabajo, on_delete= models.PROTECT, null=True, blank=True, related_name = "venta")

    def __str__(self):
        return f"Venta #{self.id} | Fecha: {self.fecha} | Total: ${self.total}"
    
class LineaProductoAbstracta(models.Model):
    cantidad_adquirida = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    # blank=True: si se deja vacío, se copia el precio de venta del producto al guardar
    precio_vendido = models.DecimalField(max_digits=10, decimal_places = 2, blank=True, validators=[MinValueValidator(0)])
    producto = models.ForeignKey(Producto, on_delete = models.PROTECT, related_name="%(class)ss")

    class Meta:
        abstract = True

    @property
    def subtotal(self):
        if(self.cantidad_adquirida is None or self.precio_vendido is None):
            return 0
        return self.cantidad_adquirida * self.precio_vendido

    def save(self, *args, **kwargs):
        if self.precio_vendido is None:
            self.precio_vendido = self.producto.precio_venta
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad_adquirida}x {self.producto} — ${self.precio_vendido}"
    
class LineaProductoVenta(LineaProductoAbstracta):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="lineas_producto")

class LineaProductoOrden(LineaProductoAbstracta):
    orden_trabajo = models.ForeignKey(OrdenTrabajo, on_delete= models.CASCADE, related_name = "lineas_producto")
