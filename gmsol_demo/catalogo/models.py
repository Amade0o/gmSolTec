"Cada clase hereda de models.Model."
"En models va cada clase que representa una tabla de la base de datos."
"Django convierte cada clase en una tabla y cada atributo en una columna. Ejemplo:"
from django.db import models

EQUIPO_RECIBIDO_ORDEN_CHOICES= [
    ('celular', 'Celular'),
    ('notebook', 'Notebook'),
    ('pc','PC')
]

MODELO_EQUIPO_TIPO_CHOICES = [
    ('celular', 'Celular'),
    ('notebook', 'Notebook')
]

EQUIPO_ORDEN_ESTADO_CHOICES = [
    ('pendiente', 'Pendiente'),
    ('arreglado', 'Arreglado'),
    ('no_arreglable', 'No Arreglable')
]

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
    # Relación 1 cliente -> 1..n teléfonos
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
        related_name="reparacion_y_tipos",
    )

    def __str__(self):
        return self.nombre

class OrdenTrabajo(models.Model):
    cliente = models.ForeignKey("Cliente", on_delete=models.PROTECT, related_name="ordenes")
    fecha_recepcion = models.DateTimeField(auto_now_add=True)

    
    @property
    def estado(self):
        # El estado de la orden depende del estado de los equipos asociados
        equipos = list(self.equipos.all())
        if not equipos: 
            return 'pendiente'


        if all(equipo.estado == 'arreglado' for equipo in equipos):
            return 'arreglado'
        elif all(equipo.estado == 'no_arreglable' for equipo in equipos):
            return 'no_arreglable'
        elif not any(equipo.estado == 'pendiente' for equipo in equipos):
            return 'arreglado'
        else:
            return 'pendiente'

    def __str__(self):
        return f"Orden #{self.id}"

class EquipoRecibido(models.Model):
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name="equipos")
    tipo = models.CharField(max_length=20, choices=EQUIPO_RECIBIDO_ORDEN_CHOICES)
    modelo = models.ForeignKey(ModeloEquipo, on_delete=models.PROTECT, related_name="equipos", blank = True, null = True)
    problema = models.TextField(max_length=500) 
    tipo_bloqueo = models.CharField(max_length=20, choices=BLOQUEO_CHOICES)
    clave_bloqueo = models.CharField(max_length=100, blank=True)
    accesorios_dejados = models.TextField(max_length=300, blank = True)
    estado = models.CharField(max_length=20, default= 'pendiente', choices=EQUIPO_ORDEN_ESTADO_CHOICES)

    def __str__(self):
        return f"Equipo #{self.id} | Orden #{self.orden.id}"

class LineaReparacion(models.Model):    
    precio_orden = models.DecimalField(max_digits=10, decimal_places=2)
    nota = models.TextField(max_length=300, blank=True) #opcional
    equipo = models.ForeignKey(EquipoRecibido, on_delete=models.CASCADE, related_name="lineas_reparacion")
    reparacion = models.ForeignKey(Reparacion, on_delete=models.PROTECT, related_name="lineas")

    def __str__(self):
        return f"Linea de Reparacion #{self.id}"