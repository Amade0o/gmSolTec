"""Clientes y sus teléfonos."""
from django.db import models


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
