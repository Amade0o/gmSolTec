"""Catálogo: lo que el negocio vende y repara, y las tablas que lo ordenan.

Categorías y productos, marcas, tipos y modelos de equipo, categorías de reparación y reparaciones.
El stock (cuántas unidades hay) NO está acá: es otra cosa y llega con la etapa 4.
"""
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify


class CategoriaProducto(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    activa = models.BooleanField(default=True)  # no se borra: se desactiva

    def __str__(self):
        return self.nombre


class TipoEquipo(models.Model):
    """Celular, Notebook, PC, Tablet… Lo carga el dueño en el Catálogo.
    'clave' es lo que se guarda en los equipos y modelos ("celular"): no cambia aunque cambie el nombre."""
    clave = models.SlugField(max_length=20, unique=True, editable=False)
    nombre = models.CharField(max_length=40, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "tipo de equipo"
        verbose_name_plural = "tipos de equipo"

    def save(self, *args, **kwargs):
        if not self.clave:
            base = slugify(self.nombre)[:16] or "tipo"
            clave, n = base, 2
            while TipoEquipo.objects.filter(clave=clave).exists():
                clave, n = f"{base}-{n}", n + 1
            self.clave = clave
        super().save(*args, **kwargs)

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

class ModeloEquipo(models.Model): 
    nombre = models.CharField(max_length=60)
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, related_name="modelos",
                              limit_choices_to={"activa": True})
    tipo = models.ForeignKey(TipoEquipo, to_field="clave", db_column="tipo", on_delete=models.PROTECT,
                             related_name="modelos", limit_choices_to={"activo": True})
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

    NOMBRE_REVISION = "Revisión / diagnóstico"

    @property
    def es_revision(self):
        """La revisión va una sola vez por equipo (es la primera línea de todo equipo)."""
        return self.nombre.casefold() == self.NOMBRE_REVISION.casefold()

    def __str__(self):
        return self.nombre
