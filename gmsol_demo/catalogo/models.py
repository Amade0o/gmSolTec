from django.contrib import admin

"Cada clase hereda de models.Model."
"En models va cada clase que representa una tabla de la base de datos."
"Django convierte cada clase en una tabla y cada atributo en una columna. Ejemplo:"
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

#Tipos de equipos que se pueden recibir en una orden de trabajo
EQUIPO_RECIBIDO_ORDEN_CHOICES= [
    ('celular', 'Celular'),
    ('notebook', 'Notebook'),
    ('pc','PC')
]

# Tipos de equipo que registramos en la base de datos
MODELO_EQUIPO_TIPO_CHOICES = [
    ('celular', 'Celular'),
    ('notebook', 'Notebook')
]

# Estados del equipo dentro de la orden, estos tambien seran estados de la orden
EQUIPO_ORDEN_ESTADO_CHOICES = [
    ('pendiente', 'Pendiente'),
    ('sin_falla', 'Sin falla'),
    ('arreglado', 'Arreglado'),
    ('no_arreglable', 'No Arreglable')
]

# Tipos de pago que puede tener una orden de trabajo
CUENTA_CHOICES = [
    ('efectivo', 'Efectivo'),
    ('digital', 'Digital')
]

# Tipos de bloqueo que puede tener un equipo
BLOQUEO_CHOICES = [
    ('pin', 'Pin'),
    ('patron', 'Patron'),
    ('contrasena', 'Contrasena'),
    ('ninguno', 'Ninguno')
]


class CategoriaProducto(models.Model):
    nombre = models.CharField(max_length=60)
    activa = models.BooleanField(default=True)  # no se borra: se desactiva

    def __str__(self):
        return self.nombre


class Marca(models.Model):
    nombre = models.CharField(max_length=60)
    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    nombre = models.CharField(max_length=120)
    # Relación 0..n productos -> 1 categoría (obligatoria)
    categoria = models.ForeignKey(
        CategoriaProducto, on_delete=models.PROTECT, related_name="productos"
    )
    # Relación 0..n productos -> 0..1 marca (opcional)
    marca = models.ForeignKey(
        Marca, on_delete=models.PROTECT, null=True, blank=True, related_name="productos"
    )
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)

    @property
    def margen(self):
        # El margen NO se guarda: se calcula con los dos precios
        if self.precio_compra:
            return round((self.precio_venta - self.precio_compra) / self.precio_compra * 100, 1)
        return None

    def __str__(self):
        return self.nombre


class Cliente(models.Model):
    nombre = models.CharField(max_length=120)
    notas = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.nombre


class Telefono(models.Model):
    # Relación - cliente -> 0..n teléfonos
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="telefonos")
    numero = models.CharField(max_length=30)
    principal = models.BooleanField(default=False)

    def __str__(self):
        return self.numero

class ModeloEquipo(models.Model): 
    nombre = models.CharField(max_length=60)
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, related_name="modelos") 
    tipo = models.CharField(max_length=20, choices= MODELO_EQUIPO_TIPO_CHOICES)
    activo = models.BooleanField(default=True)
    

    def __str__(self):
        return f"{self.nombre} | {self.marca} | {self.tipo}"

class CategoriaReparacion(models.Model):  
    nombre = models.CharField(max_length=60)
    activo = models.BooleanField(default=True)

    
    def __str__(self):
        return self.nombre

class Reparacion(models.Model): 
    nombre = models.CharField(max_length=60)
    activo = models.BooleanField(default=True)
    categoria = models.ForeignKey(
        CategoriaReparacion,
        on_delete=models.PROTECT,
        related_name="reparaciones",
    )

    def __str__(self):
        return self.nombre

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
            return 'no_arreglable'

        return 'lista'  

    @property
    def total(self):
        total = 0 

        for equipo in self.equipos.all():
            for linea in equipo.lineas_reparacion.all():
                total += linea.subtotal

        for linea in self.lineas_producto.all():
            total += linea.subtotal
            
        return total

    @property
    def monto_pagado(self):
        total = Decimal("0.00")

        for pago in self.pagos.all():
            total += pago.monto
        return total

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

class MetodoPago(models.Model):
    nombre = models.CharField(max_length=60) 
    cuenta = models.CharField(max_length=20, choices=CUENTA_CHOICES)
    recargo_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default = 0,validators=[MinValueValidator(0)])
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} | {self.cuenta} | {self.recargo_porcentaje}%"

class Pago(models.Model):
    orden_trabajo = models.ForeignKey(OrdenTrabajo, on_delete=models.PROTECT,related_name="pagos", null = True, blank = True) #null y blank son para que no sea obligatorio, ya que se puede crear un pago sin orden de trabajo
    metodo_pago = models.ForeignKey(MetodoPago, on_delete=models.PROTECT, related_name="pagos")
    venta = models.ForeignKey("Venta", on_delete=models.PROTECT, null=True, blank=True, related_name="pagos")
    monto = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    recargo_porcentaje = models.DecimalField(max_digits= 5, decimal_places=2, blank=True, validators=[MinValueValidator(0)])
    fecha = models.DateTimeField(auto_now_add=True)

    @property
    def recargo_monto(self):
        if self.monto is None or self.recargo_porcentaje is None:
            return Decimal("0.00")
        
        return self.monto * (self.recargo_porcentaje / Decimal("100"))
 
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

    #Esto es para que el Pago no pueda ser de una venta y de una orden de trabajo a la vez
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(orden_trabajo__isnull=False, venta__isnull=True)
                           | models.Q(orden_trabajo__isnull=True, venta__isnull=False)),
                name="pago_orden_o_venta",
            )
        ]

    def clean(self):
       super().clean()
       if self.orden_trabajo_id and self.venta_id:
           raise ValidationError("El pago pertenece a una orden o a una venta, no a las dos.")

     



class EquipoRecibido(models.Model):
    orden_trabajo = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name="equipos")
    tipo = models.CharField(max_length=20, choices=EQUIPO_RECIBIDO_ORDEN_CHOICES)
    modelo = models.ForeignKey(ModeloEquipo, on_delete=models.PROTECT, related_name="equipos", blank = True, null = True)
    problema = models.TextField(max_length=500) 
    tipo_bloqueo = models.CharField(max_length=20, choices=BLOQUEO_CHOICES)
    clave_bloqueo = models.CharField(max_length=100, blank=True)
    accesorios_dejados = models.TextField(max_length=300, blank = True)
    estado = models.CharField(max_length=20, default= 'pendiente', choices=EQUIPO_ORDEN_ESTADO_CHOICES)

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

class Venta(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    cliente = models.ForeignKey(Cliente, on_delete= models.PROTECT, null = True, blank = True, related_name = "ventas_cliente")
    orden_trabajo = models.OneToOneField(OrdenTrabajo, on_delete= models.PROTECT, null=True, blank=True, related_name = "venta")

    def __str__(self):
        return f"Venta #{self.id} | Fecha: {self.fecha} | Total: ${self.total}"
    
class LineaProductoAbstracta(models.Model):
    cantidad_adquirida = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    precio_vendido = models.DecimalField(max_digits=10, decimal_places = 2, validators=[MinValueValidator(0)])
    producto = models.ForeignKey(Producto, on_delete = models.PROTECT, related_name="%(class)ss")

    class Meta:
        abstract = True

    @property
    def subtotal(self):
        if(self.cantidad_adquirida is None or self.precio_vendido is None):
            return 0
        return self.cantidad_adquirida * self.precio_vendido

    def __str__(self):
        return f"{self.cantidad_adquirida}x {self.producto} — ${self.precio_vendido}"
    
class LineaProductoVenta(LineaProductoAbstracta):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="lineas_producto")

class LineaProductoOrden(LineaProductoAbstracta):
    orden_trabajo = models.ForeignKey(OrdenTrabajo, on_delete= models.CASCADE, related_name = "lineas_producto")

