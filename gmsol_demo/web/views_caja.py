"""Pantallas de la caja (etapa 4) y del historial de cambios.

Como el resto de las vistas, no tienen reglas: leen el formulario, llaman a negocio/servicios/
y redirigen (así F5 no guarda dos veces). Versión mínima para probar; se pule en el paso 4.7.
"""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from negocio import servicios
from negocio.models import AREA_CHOICES, CAJA_CHOICES, CAJAS_PRINCIPALES, Cambio, MovimientoCaja
from negocio.servicios import ReglaDeNegocioError
from negocio.servicios.caja import TIPOS_MANUALES

from .forms_caja import AnularMovimientoForm, CorregirMovimientoForm, SaldoInicialForm
from .templatetags.formato import pesos

NOMBRE_CAJA = dict(CAJA_CHOICES)
CANTIDAD_MOVIMIENTOS = 100


def _avisar_error(request, error):
    for texto in (error.messages if isinstance(error, ValidationError) else [str(error)]):
        messages.error(request, texto)


@login_required
def caja(request):
    sin_saldo_inicial = [c for c in CAJAS_PRINCIPALES if not servicios.tiene_saldo_inicial(c)]

    if request.method == "POST" and request.POST.get("accion") == "saldo_inicial":
        form = SaldoInicialForm(request.POST, cajas=sin_saldo_inicial)
        if form.is_valid():
            datos = form.cleaned_data
            try:
                servicios.cargar_saldo_inicial(datos["caja"], datos["monto"], datos["nota"])
            except (ValidationError, ReglaDeNegocioError) as error:
                _avisar_error(request, error)
            else:
                messages.success(request, f"Listo: el saldo inicial de {NOMBRE_CAJA[datos['caja']]} es {pesos(datos['monto'])}.")
                return redirect("web:caja")
    else:
        form = SaldoInicialForm(cajas=sin_saldo_inicial)

    filtro = request.GET.get("caja", "")
    movimientos = MovimientoCaja.objects.all()
    if filtro in NOMBRE_CAJA:
        movimientos = movimientos.filter(caja=filtro)
    else:
        filtro = ""

    saldos = servicios.saldos()
    return render(request, "web/caja/caja.html", {
        "efectivo": saldos["efectivo"],
        "digital": saldos["digital"],
        "senas_efectivo": saldos["senas_efectivo"],
        "senas_digital": saldos["senas_digital"],
        "senas_total": saldos["senas_efectivo"] + saldos["senas_digital"],
        "movimientos": movimientos[:CANTIDAD_MOVIMIENTOS],
        "filtro": filtro,
        "cajas": CAJA_CHOICES,
        "form_saldo_inicial": form if sin_saldo_inicial else None,
        "manuales": TIPOS_MANUALES,
    })


@login_required
def movimiento_detalle(request, numero):
    movimiento = get_object_or_404(MovimientoCaja, pk=numero)
    se_puede_tocar = movimiento.tipo in TIPOS_MANUALES and not movimiento.anulado
    form_corregir = CorregirMovimientoForm(initial={"monto": movimiento.monto_absoluto, "nota": movimiento.nota})
    form_anular = AnularMovimientoForm()

    if request.method == "POST" and se_puede_tocar:
        accion = request.POST.get("accion")
        if accion == "corregir":
            form_corregir = CorregirMovimientoForm(request.POST)
            if form_corregir.is_valid():
                datos = form_corregir.cleaned_data
                try:
                    servicios.corregir_movimiento(movimiento, datos["monto"], datos["nota"])
                except (ValidationError, ReglaDeNegocioError) as error:
                    _avisar_error(request, error)
                else:
                    messages.success(request, f"Corregido: «{movimiento.descripcion}» ahora es {pesos(datos['monto'])}. "
                                              "El valor anterior quedó en el historial.")
                    return redirect("web:movimiento_caja", numero=movimiento.pk)
        elif accion == "anular":
            form_anular = AnularMovimientoForm(request.POST)
            if form_anular.is_valid():
                try:
                    servicios.anular_movimiento(movimiento, form_anular.cleaned_data["motivo"])
                except (ValidationError, ReglaDeNegocioError) as error:
                    _avisar_error(request, error)
                else:
                    messages.success(request, f"Anulado: «{movimiento.descripcion}» ya no suma en la caja. Queda tachado y en el historial.")
                    return redirect("web:caja")

    return render(request, "web/caja/movimiento.html", {
        "movimiento": movimiento,
        "se_puede_tocar": se_puede_tocar,
        "form_corregir": form_corregir,
        "form_anular": form_anular,
        "cambios": movimiento.cambios.all(),
    })


PERIODOS = [("hoy", "Hoy"), ("semana", "Últimos 7 días"), ("mes", "Este mes"), ("todo", "Todo")]
CANTIDAD_HISTORIAL = 300


@login_required
def historial(request):
    area = request.GET.get("area", "")
    periodo = request.GET.get("periodo", "semana")
    cambios = Cambio.objects.select_related("movimiento_caja")
    if area in dict(AREA_CHOICES):
        cambios = cambios.filter(area=area)
    else:
        area = ""
    ahora = timezone.localtime()
    desde = {
        "hoy": ahora.replace(hour=0, minute=0, second=0, microsecond=0),
        "semana": ahora - timedelta(days=7),
        "mes": ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
    }.get(periodo)
    if desde is not None:
        cambios = cambios.filter(fecha__gte=desde)
    elif periodo != "todo":
        periodo = "semana"
        cambios = cambios.filter(fecha__gte=ahora - timedelta(days=7))
    return render(request, "web/historial.html", {
        "dias": _por_dia(cambios[:CANTIDAD_HISTORIAL]),
        "area": area, "areas": AREA_CHOICES,
        "periodo": periodo, "periodos": PERIODOS,
    })


def _por_dia(cambios):
    """[(día, [cambios de ese día]), …], del más nuevo al más viejo. El día es el de Argentina
    (TIME_ZONE): agrupar con la fecha guardada en UTC pondría lo de la noche en el día siguiente."""
    dias = []
    for cambio in cambios:
        dia = timezone.localtime(cambio.fecha).date()
        if not dias or dias[-1][0] != dia:
            dias.append((dia, []))
        dias[-1][1].append(cambio)
    return dias
