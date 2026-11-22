"""Servicio del historial: anotar, en una frase, lo que se cargó, corrigió o anuló.

Lo llaman los otros servicios en la misma transacción que el cambio: si el cambio no se guarda,
la frase tampoco (y al revés).
"""
from ..models import Cambio


def anotar(area, accion, frase, antes="", despues="", movimiento_caja=None):
    cambio = Cambio(area=area, accion=accion, frase=frase, antes=antes, despues=despues,
                    movimiento_caja=movimiento_caja)
    cambio.full_clean()
    cambio.save()
    return cambio
