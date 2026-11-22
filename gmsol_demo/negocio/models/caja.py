"""Caja: dónde está la plata del negocio y cada entrada o salida.

Regla principal (etapa 4, ver CLAUDE/DISEÑO/etapa-4-caja.md):
    El saldo de una caja es la SUMA de sus movimientos no anulados. No hay otra cuenta.

Hay cuatro cajas:
    efectivo         billetes del local, disponibles
    digital          banco + Mercado Pago + Naranja X, todo junto, disponible
    senas_efectivo   señas en efectivo de órdenes abiertas (el dueño las aparta, no las usa)
    senas_digital    señas que entraron por transferencia o tarjeta (están en el banco, pero no se usan)

Los movimientos no se borran nunca: si algo se cargó por error se ANULA (queda tachado y no suma).
Corregir el monto de un movimiento cargado a mano se permite; el antes y el después quedan en el
historial (modelo Cambio). Todo eso lo hacen los servicios (negocio/servicios/caja.py): este archivo
solo define los datos y sus reglas básicas.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from ..formato import pesos

CAJA_CHOICES = [
    ("efectivo", "Efectivo"),
    ("digital", "Digital"),
    ("senas_efectivo", "Señas en efectivo"),
    ("senas_digital", "Señas en digital"),
]
CAJAS_PRINCIPALES = ("efectivo", "digital")
CAJAS_SENAS = ("senas_efectivo", "senas_digital")

TIPO_MOVIMIENTO_CHOICES = [
    ("saldo_inicial", "Saldo inicial"),
    ("sena", "Seña de una orden"),
    ("pase_sena", "La seña pasa a la caja"),
    ("cobro", "Cobro"),
    ("devolucion", "Devolución al cliente"),
    ("retiro", "Retiro del dueño"),
    ("gasto", "Gasto del negocio"),
    ("compra_mercaderia", "Compra de mercadería"),
    ("pase", "Pase entre cajas"),
    ("ajuste", "Ajuste por conteo"),
]

# Signo obligatorio de cada tipo: +1 siempre entra, -1 siempre sale. Los que no están
# (pases y ajustes) pueden ir para los dos lados.
SIGNO_DEL_TIPO = {
    "saldo_inicial": 1,
    "sena": 1,
    "cobro": 1,
    "devolucion": -1,
    "retiro": -1,
    "gasto": -1,
    "compra_mercaderia": -1,
}

# En qué cajas puede ir cada tipo (si no está, en cualquiera)
CAJAS_DEL_TIPO = {
    "saldo_inicial": CAJAS_PRINCIPALES,     # las señas se forman solas con las órdenes abiertas
    "sena": CAJAS_SENAS,
    "cobro": CAJAS_PRINCIPALES,
    "retiro": CAJAS_PRINCIPALES,            # el dueño no usa la plata de las señas
    "gasto": CAJAS_PRINCIPALES,
    "compra_mercaderia": CAJAS_PRINCIPALES,
}


class MovimientoCaja(models.Model):
    """Una entrada (+) o salida (−) de plata en una caja."""
    fecha = models.DateTimeField(default=timezone.now)
    caja = models.CharField(max_length=20, choices=CAJA_CHOICES)
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO_CHOICES)
    # Con signo: positivo entra, negativo sale. Así el saldo es una suma simple.
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    # Texto que arma el sistema ("Saldo inicial de Efectivo"); la nota la escribe el dueño
    descripcion = models.CharField(max_length=200)
    nota = models.CharField(max_length=300, blank=True)
    anulado = models.BooleanField(default=False)
    anulado_fecha = models.DateTimeField(null=True, blank=True)
    anulado_motivo = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "movimiento de caja"
        verbose_name_plural = "movimientos de caja"
        indexes = [models.Index(fields=["caja", "anulado"], name="movcaja_caja_anulado")]

    def clean(self):
        super().clean()
        if self.monto is None or self.monto == 0:
            raise ValidationError({"monto": "El monto no puede ser 0."})
        signo = SIGNO_DEL_TIPO.get(self.tipo)
        if signo == 1 and self.monto < 0:
            raise ValidationError({"monto": f"«{self.get_tipo_display()}» siempre entra a la caja: el monto va en positivo."})
        if signo == -1 and self.monto > 0:
            raise ValidationError({"monto": f"«{self.get_tipo_display()}» siempre sale de la caja: el monto va en negativo."})
        cajas = CAJAS_DEL_TIPO.get(self.tipo)
        if cajas and self.caja not in cajas:
            raise ValidationError({"caja": f"«{self.get_tipo_display()}» no puede ir en «{self.get_caja_display()}»."})
        if self.anulado and not self.anulado_fecha:
            raise ValidationError("Un movimiento anulado tiene que tener la fecha de anulación.")

    def delete(self, *args, **kwargs):
        raise ValidationError("Los movimientos de caja no se borran: se anulan.")

    @property
    def es_entrada(self):
        return self.monto > 0

    @property
    def monto_absoluto(self):
        return abs(self.monto) if self.monto is not None else Decimal("0.00")

    def __str__(self):
        estado = " (anulado)" if self.anulado else ""
        sentido = "entra" if self.es_entrada else "sale"
        return f"Movimiento #{self.id} | {self.get_caja_display()} | {self.descripcion} | {sentido} {pesos(self.monto)}{estado}"
