"""Historial de cambios: cada cosa que el dueño carga, corrige o anula queda escrita en una frase.

Es lo que permite corregir sin miedo: el valor anterior nunca se pierde. Un renglón del historial
no se modifica ni se borra (lo controla este modelo).
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .caja import MovimientoCaja

AREA_CHOICES = [
    ("dinero", "Dinero"),
    ("stock", "Stock"),
    ("ordenes", "Órdenes"),
]

ACCION_CHOICES = [
    ("alta", "Se cargó"),
    ("correccion", "Se corrigió"),
    ("anulacion", "Se anuló"),
]


class Cambio(models.Model):
    """Un renglón del historial: qué pasó, en palabras, con el antes y el después."""
    fecha = models.DateTimeField(default=timezone.now)
    area = models.CharField(max_length=20, choices=AREA_CHOICES)
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES)
    frase = models.CharField(max_length=300)
    antes = models.CharField(max_length=200, blank=True)
    despues = models.CharField(max_length=200, blank=True)
    movimiento_caja = models.ForeignKey(
        MovimientoCaja, on_delete=models.PROTECT, null=True, blank=True, related_name="cambios")

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "cambio del historial"
        verbose_name_plural = "historial de cambios"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("El historial no se modifica: cada cambio queda como se escribió.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("El historial no se borra.")

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y %H:%M} | {self.frase}"
