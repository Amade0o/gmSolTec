"""Formularios de la pantalla Caja. Solo leen lo que se escribe: las reglas están en
negocio/servicios/caja.py."""
from decimal import Decimal

from django import forms

from negocio.models import CAJA_CHOICES, CAJAS_PRINCIPALES

NOMBRE_CAJA = dict(CAJA_CHOICES)


def _monto(label, ayuda=""):
    return forms.DecimalField(
        label=label, help_text=ayuda, max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={"inputmode": "decimal", "step": "0.01", "placeholder": "Ej.: 150000"}))


class SaldoInicialForm(forms.Form):
    caja = forms.ChoiceField(label="Caja")
    monto = _monto("¿Cuánto hay?", "Lo que hay hoy en esa caja, contado o mirado en la app del banco.")
    nota = forms.CharField(label="Nota (opcional)", max_length=300, required=False)

    def __init__(self, *args, cajas=CAJAS_PRINCIPALES, **kwargs):
        """cajas: las que todavía no tienen saldo inicial."""
        super().__init__(*args, **kwargs)
        self.fields["caja"].choices = [(c, NOMBRE_CAJA[c]) for c in cajas]


class CorregirMovimientoForm(forms.Form):
    monto = _monto("Monto correcto", "Escribilo en positivo: si es una salida, el sistema ya sabe que resta.")
    nota = forms.CharField(label="Nota", max_length=300, required=False)


class AnularMovimientoForm(forms.Form):
    motivo = forms.CharField(label="¿Por qué se anula? (opcional)", max_length=200, required=False,
                             widget=forms.TextInput(attrs={"placeholder": "Ej.: lo cargué dos veces"}))
