"""Servicios de la caja: saldos, saldo inicial, corregir y anular.

Reglas (ver CLAUDE/DISEÑO/etapa-4-caja.md):
1. El saldo de una caja es la suma de sus movimientos no anulados. Nada más.
2. Ningún movimiento, corrección ni anulación puede dejar una caja en negativo.
3. Los movimientos no se borran: se anulan. Cada alta, corrección o anulación queda en el historial,
   dentro de la misma transacción.
4. `registrar_movimiento` es el único lugar que crea movimientos: así el control del punto 2
   no se puede saltear.

Sobre la suma: SQLite guarda los decimales como número con coma flotante, así que la suma se hace
en Python con Decimal (cada monto llega redondeado a centavos). Así nunca aparece un centavo de más.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ..formato import pesos
from ..models import CAJA_CHOICES, CAJAS_PRINCIPALES, SIGNO_DEL_TIPO, MovimientoCaja
from .comun import ReglaDeNegocioError
from .historial import anotar

CERO = Decimal("0.00")
NOMBRE_CAJA = dict(CAJA_CHOICES)

# Lo que el dueño carga a mano desde la caja: se corrige o se anula desde la caja.
# Lo que nace de un pago, una devolución o una venta se corrige desde ahí (paso 4.2).
TIPOS_MANUALES = ("saldo_inicial", "retiro", "gasto", "compra_mercaderia")


def _exigir_caja(caja):
    if caja not in NOMBRE_CAJA:
        raise ReglaDeNegocioError("Esa caja no existe.")


def saldo_de(caja):
    """Lo que hay en una caja: la suma de sus movimientos no anulados."""
    _exigir_caja(caja)
    montos = MovimientoCaja.objects.filter(caja=caja, anulado=False).values_list("monto", flat=True)
    return sum(montos, CERO)


def saldos():
    """El saldo de las cuatro cajas, con una sola consulta. Es la misma suma que `saldo_de`."""
    totales = {caja: CERO for caja in NOMBRE_CAJA}
    for caja, monto in MovimientoCaja.objects.filter(anulado=False).values_list("caja", "monto"):
        totales[caja] += monto
    return totales


def tiene_saldo_inicial(caja):
    return MovimientoCaja.objects.filter(caja=caja, tipo="saldo_inicial", anulado=False).exists()


def _exigir_que_no_quede_negativa(caja, variacion, que_pasaria):
    """Si `variacion` resta plata, controla que la caja no quede en negativo."""
    if variacion >= 0:
        return
    hay = saldo_de(caja)
    if hay + variacion < 0:
        raise ReglaDeNegocioError(
            f"En {NOMBRE_CAJA[caja]} hay {pesos(hay)}: {que_pasaria} quedaría en negativo "
            f"(faltarían {pesos(hay + variacion)}). Revisá si esa plata salió de otra caja.")


def registrar_movimiento(caja, tipo, monto, descripcion, nota=""):
    """Crea un movimiento (el único lugar que lo hace). El monto va con signo: + entra, − sale."""
    _exigir_caja(caja)
    movimiento = MovimientoCaja(caja=caja, tipo=tipo, monto=monto, descripcion=descripcion,
                                nota=(nota or "").strip(), fecha=timezone.now())
    movimiento.full_clean()     # monto distinto de 0, signo y caja que corresponden al tipo
    _exigir_que_no_quede_negativa(caja, movimiento.monto, f"si salen {pesos(-movimiento.monto)}, la caja")
    movimiento.save()
    return movimiento


@transaction.atomic
def cargar_saldo_inicial(caja, monto, nota=""):
    """Lo que hay en Efectivo o en Digital el día que se empieza a usar el sistema."""
    _exigir_caja(caja)
    if caja not in CAJAS_PRINCIPALES:
        raise ReglaDeNegocioError("El saldo inicial se carga solo en Efectivo o en Digital: "
                                  "las señas se forman solas con las órdenes abiertas.")
    if monto is None or monto <= 0:
        raise ReglaDeNegocioError("El saldo inicial tiene que ser mayor a $ 0. Si en esa caja no hay nada, no hace falta cargarlo.")
    if tiene_saldo_inicial(caja):
        raise ReglaDeNegocioError(f"{NOMBRE_CAJA[caja]} ya tiene saldo inicial. Si está mal, corregilo.")
    nombre = NOMBRE_CAJA[caja]
    movimiento = registrar_movimiento(caja, "saldo_inicial", monto, f"Saldo inicial de {nombre}", nota)
    anotar("dinero", "alta", f"Cargaste el saldo inicial de {nombre}: {pesos(monto)}.",
           despues=pesos(monto), movimiento_caja=movimiento)
    return movimiento


def _exigir_manual(movimiento, accion):
    if movimiento.tipo not in TIPOS_MANUALES:
        raise ReglaDeNegocioError(
            f"«{movimiento.descripcion}» no se {accion} desde la caja: se hace desde donde se cargó "
            "(la orden, la venta o la devolución).")


@transaction.atomic
def corregir_movimiento(movimiento, monto, nota=None):
    """Cambia el monto (y, si viene, la nota) de un movimiento cargado a mano.

    `monto` es lo que escribe el dueño, siempre en positivo: el signo lo pone el tipo
    (un retiro de $ 5.000 se guarda como −5.000). El valor anterior queda en el historial."""
    movimiento = MovimientoCaja.objects.get(pk=movimiento.pk)       # siempre con los datos guardados
    _exigir_manual(movimiento, "corrige")
    if movimiento.anulado:
        raise ReglaDeNegocioError("Este movimiento está anulado: no se corrige.")
    if monto is None or monto <= 0:
        raise ReglaDeNegocioError("Escribí el monto correcto (mayor a $ 0).")
    nuevo = SIGNO_DEL_TIPO[movimiento.tipo] * monto
    nota_nueva = movimiento.nota if nota is None else nota.strip()
    if nuevo == movimiento.monto and nota_nueva == movimiento.nota:
        raise ReglaDeNegocioError("No cambiaste nada: el monto y la nota son los mismos.")

    monto_anterior, nota_anterior = movimiento.monto, movimiento.nota
    _exigir_que_no_quede_negativa(movimiento.caja, nuevo - monto_anterior, "con esta corrección, la caja")
    movimiento.monto, movimiento.nota = nuevo, nota_nueva
    movimiento.full_clean()
    movimiento.save()

    caja = NOMBRE_CAJA[movimiento.caja]
    if nuevo != monto_anterior:
        anotar("dinero", "correccion",
               f"Corregiste «{movimiento.descripcion}» ({caja}): de {pesos(monto_anterior)} a {pesos(nuevo)}.",
               antes=pesos(monto_anterior), despues=pesos(nuevo), movimiento_caja=movimiento)
    if nota_nueva != nota_anterior:
        anotar("dinero", "correccion", f"Cambiaste la nota de «{movimiento.descripcion}» ({caja}).",
               antes=_recortar(nota_anterior), despues=_recortar(nota_nueva), movimiento_caja=movimiento)
    return movimiento


@transaction.atomic
def anular_movimiento(movimiento, motivo=""):
    """Un movimiento cargado por error: deja de sumar, queda tachado y nunca se borra."""
    movimiento = MovimientoCaja.objects.get(pk=movimiento.pk)
    _exigir_manual(movimiento, "anula")
    if movimiento.anulado:
        raise ReglaDeNegocioError("Este movimiento ya está anulado.")
    _exigir_que_no_quede_negativa(movimiento.caja, -movimiento.monto, "si lo anulás, la caja")
    motivo = (motivo or "").strip()
    movimiento.anulado = True
    movimiento.anulado_fecha = timezone.now()
    movimiento.anulado_motivo = motivo
    movimiento.full_clean()
    movimiento.save()
    caja = NOMBRE_CAJA[movimiento.caja]
    frase = f"Anulaste «{movimiento.descripcion}» ({caja}, {pesos(movimiento.monto)})."
    if motivo:
        frase += f" Motivo: {motivo}"
    anotar("dinero", "anulacion", _recortar(frase, 300), antes=pesos(movimiento.monto), despues="Anulado",
           movimiento_caja=movimiento)
    return movimiento


def _recortar(texto, largo=200):
    """Los campos del historial tienen un largo máximo: un texto muy largo se corta con «…»."""
    texto = texto or ""
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"
