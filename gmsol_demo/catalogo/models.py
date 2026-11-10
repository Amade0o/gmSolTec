from django.contrib import admin

"Cada clase hereda de models.Model."
"En models va cada clase que representa una tabla de la base de datos."
"Django convierte cada clase en una tabla y cada atributo en una columna. Ejemplo:"
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

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
    ('pendiente', 'En revisión / reparación'),
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
    nombre = models.CharField(max_length=60, unique=True)
    activa = models.BooleanField(default=True)  # no se borra: se desactiva

    def __str__(self):
        return self.nombre


class Marca(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    # Relación 0..n productos -> 1 categoría (obligatoria)
    # limit_choices_to: en los desplegables solo aparecen las activas
    categoria = models.ForeignKey(
        CategoriaProducto, on_delete=models.PROTECT, related_name="productos",
        limit_choices_to={"activa": True}
    )
    # Relación 0..n productos -> 0..1 marca (opcional)
    marca = models.ForeignKey(
        Marca, on_delete=models.PROTECT, null=True, blank=True, related_name="productos",
        limit_choices_to={"activa": True}
    )
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
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
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, related_name="modelos",
                              limit_choices_to={"activa": True})
    tipo = models.CharField(max_length=20, choices= MODELO_EQUIPO_TIPO_CHOICES)
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["marca", "nombre"], name="modelo_unico_por_marca")
        ]

    def __str__(self):
        return f"{self.nombre} | {self.marca} | {self.tipo}"

class CategoriaReparacion(models.Model):  
    nombre = models.CharField(max_length=60, unique=True)
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
        limit_choices_to={"activo": True},
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["categoria", "nombre"], name="reparacion_unica_por_categoria")
        ]

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
            # Si no queda dinero retenido (nunca hubo seña o ya se devolvió), terminó sin venta
            if self.monto_retenido == 0:
                return 'finalizada'
            return 'no_arreglable'

        return 'lista'  

    @property
    def total(self):
        total = Decimal("0.00")

        for equipo in self.equipos.all():
            if equipo.estado == "no_arreglable":
                continue        # lo que no se arregla no se cobra
            for linea in equipo.lineas_reparacion.all():
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
        if self.linea_reparacion_id:
            linea = self.linea_reparacion
            if self.orden_trabajo_id and linea.equipo.orden_trabajo_id != self.orden_trabajo_id:
                raise ValidationError({"linea_reparacion": "Esa reparación no es de esta orden."})
            if linea.equipo.estado != "no_arreglable":
                raise ValidationError({"linea_reparacion": "Solo se puede devolver la reparación de un equipo no arreglable."})
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


class EquipoRecibido(models.Model):
    orden_trabajo = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name="equipos")
    tipo = models.CharField(max_length=20, choices=EQUIPO_RECIBIDO_ORDEN_CHOICES)
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
