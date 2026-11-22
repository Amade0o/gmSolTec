"""Vistas de la interfaz propia.

Las vistas no tienen reglas de negocio: leen los formularios, llaman a
negocio/servicios/ y muestran el resultado. Después de guardar algo se
redirige (así F5 no lo guarda dos veces).

Secciones: Inicio · Órdenes (lista, nueva, detalle, entregar) · Venta rápida ·
Devoluciones · Ventas · Clientes · Productos.
"""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, F, Max, ProtectedError, Q, Sum, Value, When
from django.db.models.functions import Replace
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from negocio import servicios
from negocio.models import (
    EQUIPO_ORDEN_ESTADO_CHOICES, Cliente, Devolucion, EquipoRecibido, LineaProductoOrden,
    CategoriaProducto, LineaReparacion, OrdenTrabajo, Pago, Producto, Reparacion,
    Telefono, Venta,
)
from negocio.servicios import ReglaDeNegocioError

from .templatetags.formato import pesos
from .forms import (
    ClienteForm, ClienteNuevoForm, ClienteOrdenForm, DevolucionForm, ElegirCliente, EntregaForm, EquipoForm, LineaProductoForm,
    LineaReparacionForm, MetodoForm, PagoForm, PagosVentaFormSet, ProductosFormSet,
    ProductoForm, ProductosVentaFormSet, ReparacionesFormSet, TelefonoForm, clientes,
)

# Lo que hace falta para calcular estado, total y saldo sin una consulta por orden
PREFETCH_ORDEN = ("equipos__modelo", "equipos__tipo", "equipos__lineas_reparacion", "lineas_producto", "pagos", "devoluciones")
EN_CURSO = ("pendiente", "lista", "no_arreglable", "finalizada")      # finalizada: falta devolver el equipo


def _mensajes_de(error):
    """Convierte un error de las reglas en una lista de textos para mostrar."""
    if isinstance(error, ValidationError):
        return error.messages
    return [str(error)]


def _avisar_error(request, error):
    for texto in _mensajes_de(error):
        messages.error(request, texto)


def _numero(valor):
    """Un id que llega en el formulario: el número, o 0 si vino vacío o con letras (0 no existe → 404).
    Sin esto, un valor como "abc" llegaba a la base y daba error 500."""
    valor = str(valor or "").strip()
    return int(valor) if valor.isdigit() else 0


def _lineas(formset):
    """Las filas completas de un formset, como objetos sin guardar (las vacías se ignoran)."""
    return [form.save(commit=False) for form in formset if form.cleaned_data]


def _total_lineas(formset):
    """Suma las filas válidas, con la misma cuenta que los modelos (subtotal)."""
    total = 0
    for form in formset.forms:
        if form.is_valid() and form.cleaned_data:
            linea = form.save(commit=False)
            if getattr(linea, "precio_vendido", None) is None and getattr(linea, "producto_id", None):
                linea.precio_vendido = linea.producto.precio_venta
            total += linea.subtotal
    return total


# ---------- Inicio ----------

@login_required
def inicio(request):
    ordenes = (
        OrdenTrabajo.objects.filter(venta__isnull=True)      # las cerradas con venta ya no están en curso
        .select_related("cliente", "venta")
        .prefetch_related(*PREFETCH_ORDEN)
        .order_by("-id")
    )
    en_curso = [o for o in ordenes if o.estado in EN_CURSO]
    contexto = {
        "ordenes": en_curso,
        "en_revision": sum(1 for o in en_curso if o.estado == "pendiente"),
        "listas": sum(1 for o in en_curso if o.estado in ("lista", "finalizada")),
        "devoluciones": Devolucion.objects.filter(fecha_devolucion__isnull=True).count(),
    }
    return render(request, "web/inicio.html", contexto)


# ---------- 7.1 Lista de órdenes ----------

FILTROS = [
    ("curso", "En curso"),
    ("pendiente", "En revisión"),
    ("lista", "Listas"),
    ("no_arreglable", "No arreglables"),
    ("cerrada", "Entregadas"),
    ("finalizada", "Sin arreglo, para devolver"),
    ("todas", "Todas"),
]


def _numero_buscado(q):
    """Si lo buscado es un número ("12" o "#12"), ese número; si no, None."""
    numero = q.lstrip("#").strip()
    return int(numero) if numero.isdigit() and len(numero) <= 9 else None


def _abrir_directo(q, numero, existe, coincide_cliente):
    """¿Se abre directo la orden/venta con ese número? Con "#" siempre (si existe). Sin "#" solo si
    ningún cliente coincide: "1234" puede ser el final de un teléfono, y entonces se muestra la lista
    (con la orden #1234 primera) en vez de saltar a una orden que quizás no era."""
    return numero is not None and existe and (q.startswith("#") or not coincide_cliente)


@login_required
def ordenes(request):
    filtro = request.GET.get("estado", "curso")
    q = request.GET.get("q", "").strip()
    numero = _numero_buscado(q)

    consulta = OrdenTrabajo.objects.select_related("cliente", "venta").order_by("-id")
    if q:
        por_cliente = Q(cliente__in=_buscar_clientes(q.lstrip("#") if numero is not None else q))
        if _abrir_directo(q, numero, OrdenTrabajo.objects.filter(pk=numero or 0).exists(),
                          numero is not None and OrdenTrabajo.objects.filter(por_cliente).exists()):
            return redirect("web:orden_detalle", numero=numero)
        if numero is not None:
            # La orden con ese número va primera; después las de clientes con ese teléfono
            consulta = (consulta.filter(por_cliente | Q(pk=numero))
                        .order_by(Case(When(pk=numero, then=0), default=1), "-id"))
        else:
            consulta = consulta.filter(por_cliente)
    if filtro == "cerrada":
        consulta = consulta.filter(venta__isnull=False)
    elif filtro != "todas":
        consulta = consulta.filter(venta__isnull=True)
    consulta = consulta.prefetch_related(*PREFETCH_ORDEN)

    if filtro in ("cerrada", "todas"):
        # Sin filtro por estado: la base devuelve solo las 50 de la página (las entregadas crecen sin fin)
        lista = consulta
    else:
        # El estado se calcula (no está en la base), por eso se filtra acá. Son solo las abiertas.
        lista = [o for o in consulta if o.estado in EN_CURSO] if filtro == "curso" else \
                [o for o in consulta if o.estado == filtro]

    pagina = Paginator(lista, 50).get_page(request.GET.get("pagina"))
    return render(request, "web/ordenes/lista.html", {
        "pagina": pagina, "filtros": FILTROS, "filtro": filtro, "q": q,
    })


# ---------- 7.2 Nueva orden ----------

def _revision_inicial():
    """La primera reparación viene cargada con "Revisión / diagnóstico" a $0 (editable)."""
    revision = Reparacion.objects.filter(activo=True, nombre__iexact="Revisión / diagnóstico").first()
    return [{"reparacion": revision.pk, "precio_vendido": 0}] if revision else None


def _formularios_nueva_orden(datos=None, cliente=None):
    return {
        # ?cliente=<n> (desde la ficha del cliente) lo deja elegido
        "cliente_form": ClienteOrdenForm(datos, prefix="cli", initial={"cliente": cliente}),
        "equipo_form": EquipoForm(datos, prefix="eq"),
        "reparaciones": ReparacionesFormSet(datos, prefix="rep", initial=_revision_inicial()),
        "productos": ProductosFormSet(datos, prefix="prod"),
        "sena": PagoForm(datos, prefix="sena", empty_permitted=True, use_required_attribute=False),
    }


def _cliente_de(cliente_form):
    """El cliente elegido, o uno nuevo con su teléfono como principal."""
    datos = cliente_form.cleaned_data
    if datos["cliente"]:
        return datos["cliente"]
    return servicios.crear_cliente(Cliente(nombre=datos["nuevo_nombre"]), datos["nuevo_telefono"])


@login_required
def orden_nueva(request):
    if request.method == "POST":
        f = _formularios_nueva_orden(request.POST)
        validos = [form.is_valid() for form in f.values()]       # se validan todos, para ver todos los errores
        if all(validos):
            sena = f["sena"]
            pagos = [sena.save(commit=False)] if sena.has_changed() else []
            try:
                with transaction.atomic():      # si la orden falla, tampoco se crea el cliente nuevo
                    orden = servicios.crear_orden(
                        _cliente_de(f["cliente_form"]), f["equipo_form"].save(commit=False),
                        _lineas(f["reparaciones"]), _lineas(f["productos"]), pagos)
            except (ValidationError, ReglaDeNegocioError) as error:
                _avisar_error(request, error)
            else:
                messages.success(request, f"Orden #{orden.id} creada.")
                return redirect("web:orden_detalle", numero=orden.id)
        elegido = request.POST.get("cli-cliente")
    else:
        cliente = request.GET.get("cliente", "")
        f = _formularios_nueva_orden(cliente=int(cliente) if cliente.isdigit() else None)
        elegido = cliente
    return render(request, "web/ordenes/nueva.html", {**f, "oc": _opciones_cliente("cli-cliente", elegido=elegido)})


@login_required
@require_POST
def orden_nueva_resumen(request):
    """Resumen en vivo (HTMX): se recalcula en el servidor con la misma lógica de los modelos."""
    f = _formularios_nueva_orden(request.POST)
    total = _total_lineas(f["reparaciones"]) + _total_lineas(f["productos"])
    pago = None
    if f["sena"].has_changed() and f["sena"].is_valid():
        pago = f["sena"].save(commit=False)
        if pago.recargo_porcentaje is None:
            pago.recargo_porcentaje = pago.metodo_pago.recargo_porcentaje
    pagado = pago.monto if pago else 0
    return render(request, "web/parciales/resumen_orden.html", {
        "total": total, "pago": pago, "saldo": total - pagado,
    })


# ---------- 7.3 Detalle de la orden ----------

def _orden_para_mostrar(numero):
    return get_object_or_404(
        OrdenTrabajo.objects.select_related("cliente", "venta").prefetch_related(
            "equipos__modelo__marca", "equipos__tipo", "equipos__lineas_reparacion__reparacion",
            "lineas_producto__producto", "pagos__metodo_pago", "devoluciones__metodo_pago",
            "devoluciones__linea_reparacion__reparacion", "cliente__telefonos"),
        pk=numero)


def _formularios_detalle(orden, datos=None, accion=None):
    """Los formularios chicos del detalle. Solo el de la acción enviada recibe los datos."""
    def con_datos(nombre):
        return datos if accion == nombre else None
    return {
        "reparacion_form": LineaReparacionForm(con_datos("reparacion"), prefix="rep"),
        # A qué equipo se le quiso agregar la reparación (para mostrar el error solo ahí)
        "reparacion_equipo": int(datos["equipo"]) if accion == "reparacion" and datos.get("equipo", "").isdigit() else None,
        "equipo_form": EquipoForm(con_datos("equipo"), prefix="eq"),
        "equipo_rep_form": LineaReparacionForm(con_datos("equipo"), prefix="eqrep"),
        "producto_form": LineaProductoForm(con_datos("producto"), prefix="prod"),
        "pago_form": PagoForm(con_datos("pago"), prefix="pago"),
        "devolucion_form": DevolucionForm(con_datos("devolucion"), prefix="dev", orden=orden),
    }


def _hacer_accion(request, orden, accion, f):
    """Ejecuta la acción del formulario enviado. Devuelve el mensaje de éxito,
    o None si el formulario tiene errores (se vuelven a mostrar)."""
    post = request.POST
    if accion == "estado":
        equipo = get_object_or_404(EquipoRecibido, pk=_numero(post.get("equipo")), orden_trabajo=orden)
        servicios.cambiar_estado_equipo(equipo, post.get("estado"))
        numero = list(orden.equipos.order_by("id").values_list("id", flat=True)).index(equipo.id) + 1
        nombre = f"Equipo {numero}" if orden.equipos.count() > 1 else "El equipo"
        return f"{nombre} quedó como: {equipo.get_estado_display()}."
    if accion == "reparacion":
        equipo = get_object_or_404(EquipoRecibido, pk=_numero(post.get("equipo")), orden_trabajo=orden)
        if not f["reparacion_form"].is_valid():
            return None
        servicios.agregar_reparacion(equipo, f["reparacion_form"].save(commit=False))
        return "Reparación agregada."
    if accion == "quitar_reparacion":
        linea = get_object_or_404(LineaReparacion, pk=_numero(post.get("linea")), equipo__orden_trabajo=orden)
        servicios.quitar_reparacion(linea)
        return "Reparación quitada."
    if accion == "equipo":
        if not (f["equipo_form"].is_valid() & f["equipo_rep_form"].is_valid()):
            return None
        servicios.agregar_equipo(orden, f["equipo_form"].save(commit=False), [f["equipo_rep_form"].save(commit=False)])
        return "Equipo agregado."
    if accion == "producto":
        if not f["producto_form"].is_valid():
            return None
        servicios.agregar_producto(orden, f["producto_form"].save(commit=False))
        return "Producto agregado."
    if accion == "quitar_producto":
        linea = get_object_or_404(LineaProductoOrden, pk=_numero(post.get("linea")), orden_trabajo=orden)
        servicios.quitar_producto(linea)
        return "Producto quitado."
    if accion == "pago":
        if not f["pago_form"].is_valid():
            return None
        datos = f["pago_form"].cleaned_data
        servicios.agregar_pago(orden, datos["metodo_pago"], datos["monto"], datos["recargo_porcentaje"])
        return "Pago registrado."
    if accion == "quitar_pago":
        pago = get_object_or_404(Pago, pk=_numero(post.get("pago")), orden_trabajo=orden)
        servicios.quitar_pago(pago)
        return f"Se quitó el pago de {pesos(pago.monto)}."
    if accion == "anular_devolucion":
        devolucion = get_object_or_404(Devolucion, pk=_numero(post.get("devolucion")), orden_trabajo=orden)
        servicios.anular_devolucion(devolucion)
        return "Se anuló la devolución."
    if accion == "quitar_equipo":
        equipo = get_object_or_404(EquipoRecibido, pk=_numero(post.get("equipo")), orden_trabajo=orden)
        servicios.quitar_equipo(equipo)
        return "Se quitó el equipo de la orden."
    if accion == "devolver_saldo":
        metodo_form = MetodoForm(post, prefix="dv")
        if not metodo_form.is_valid():
            raise ReglaDeNegocioError("Elegí con qué le devolvés el dinero.")
        devuelto = servicios.devolver_saldo_a_favor(orden, metodo_form.cleaned_data["metodo_pago"])
        return f"Le devolviste {pesos(devuelto)} al cliente."
    if accion == "devolucion":
        if not f["devolucion_form"].is_valid():
            return None
        datos = f["devolucion_form"].cleaned_data
        if datos["linea_reparacion"] and datos["monto"] is None:
            # Reparación sin monto: sale del total y se devuelve lo que el cliente pagó de más por ella
            servicios.devolver_reparacion(datos["linea_reparacion"], nota=datos["nota"])
        else:
            servicios.registrar_devolucion(orden, datos["monto"], datos["linea_reparacion"], datos["nota"])
        return "Devolución registrada: queda pendiente de hacer en Devoluciones."
    raise ReglaDeNegocioError("Acción desconocida.")


@login_required
def orden_detalle(request, numero):
    f = None
    if request.method == "POST" and request.POST.get("accion") == "eliminar_orden":
        try:
            servicios.eliminar_orden(get_object_or_404(OrdenTrabajo, pk=numero))
        except ReglaDeNegocioError as error:
            _avisar_error(request, error)
            return redirect("web:orden_detalle", numero=numero)
        messages.success(request, f"Se eliminó la orden #{numero}.")
        return redirect("web:ordenes")
    if request.method == "POST":
        orden = get_object_or_404(OrdenTrabajo, pk=numero)
        accion = request.POST.get("accion")
        f = _formularios_detalle(orden, request.POST, accion)
        try:
            with transaction.atomic():
                exito = _hacer_accion(request, orden, accion, f)
        except (ValidationError, ReglaDeNegocioError) as error:
            _avisar_error(request, error)
        else:
            if exito:
                messages.success(request, exito)
                return redirect("web:orden_detalle", numero=numero)

    orden = _orden_para_mostrar(numero)
    if f is None:
        f = _formularios_detalle(orden)
    # Un formulario "Agregar reparación" por equipo. Mismo prefijo (lo que se envía no cambia),
    # pero cada uno con sus propios id: si no, las etiquetas del 2.º equipo apuntaban al 1.º.
    for equipo in orden.equipos.all():
        ya_tiene_revision = any(l.reparacion.es_revision for l in equipo.lineas_reparacion.all())
        equipo.form_reparacion = (f["reparacion_form"] if equipo.id == f["reparacion_equipo"]
                                  else LineaReparacionForm(prefix="rep", auto_id=f"id_eq{equipo.id}_%s",
                                                           sin_revision=ya_tiene_revision))
    return render(request, "web/ordenes/detalle.html", {
        "orden": orden, "estados_equipo": EQUIPO_ORDEN_ESTADO_CHOICES, **f,
        "metodo_devolucion": MetodoForm(prefix="dv"),
    })


# ---------- 7.5 Entregar ----------

@login_required
def entregar(request):
    """Órdenes listas para entregar (y búsqueda entre las abiertas)."""
    q = request.GET.get("q", "").strip()
    consulta = (OrdenTrabajo.objects.filter(venta__isnull=True).select_related("cliente", "venta")
                .prefetch_related(*PREFETCH_ORDEN).order_by("-id"))
    if q:
        numero = _numero_buscado(q)
        filtro = Q(cliente__in=_buscar_clientes(q.lstrip("#") if numero is not None else q))
        if numero is not None:
            filtro |= Q(pk=numero)
        consulta = consulta.filter(filtro)
        lista = [o for o in consulta if o.estado in EN_CURSO]
    else:
        lista = [o for o in consulta if o.estado in ("lista", "finalizada")]
    return render(request, "web/entregar.html", {"ordenes": lista, "q": q})


@login_required
def orden_entregar(request, numero):
    orden = get_object_or_404(OrdenTrabajo, pk=numero)
    if orden.cerrada:
        messages.info(request, f"La orden #{orden.id} ya se entregó.")
        return redirect("web:orden_detalle", numero=orden.id)
    form = EntregaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            venta = servicios.entregar_orden(
                orden, form.cleaned_data["metodo_pago"], form.cleaned_data["recargo_porcentaje"])
        except (ValidationError, ReglaDeNegocioError) as error:
            _avisar_error(request, error)
        else:
            if venta.total:
                messages.success(request, f"Orden #{orden.id} entregada. Venta #{venta.id} registrada.")
            else:
                messages.success(request, f"Orden #{orden.id} cerrada: se le devolvió el equipo al cliente, sin cargo.")
            return redirect("web:orden_detalle", numero=orden.id)
    return render(request, "web/ordenes/entregar.html", {"orden": _orden_para_mostrar(numero), "form": form})


# ---------- 7.4 Venta rápida ----------

def _formularios_venta(datos=None):
    cliente = ElegirCliente(queryset=clientes(), required=False, empty_label="Sin cliente")
    return {
        "productos": ProductosVentaFormSet(datos, prefix="prod"),
        "pagos": PagosVentaFormSet(datos, prefix="pago"),
        "cliente_campo": cliente,
    }


def _pagos_de_venta(formset, total):
    """Arma los Pago de la venta. Un pago con el monto vacío se lleva lo que falta."""
    pagos = [Pago(metodo_pago=d["metodo_pago"], monto=d["monto"], recargo_porcentaje=d["recargo_porcentaje"])
             for d in (form.cleaned_data for form in formset) if d]
    sin_monto = [p for p in pagos if p.monto is None]
    if len(sin_monto) > 1:
        raise ReglaDeNegocioError("Solo un pago puede quedar con el monto vacío.")
    if sin_monto:
        sin_monto[0].monto = total - sum(p.monto for p in pagos if p.monto is not None)
        if sin_monto[0].monto <= 0:
            raise ReglaDeNegocioError("Los otros pagos ya cubren el total: quitá el pago vacío.")
    return pagos


def _cliente_venta(request, campo):
    try:
        return campo.clean(request.POST.get("cliente") or None)
    except ValidationError:
        return None


@login_required
def venta_rapida(request):
    f = _formularios_venta(request.POST if request.method == "POST" else None)
    cliente_elegido = None
    if request.method == "POST":
        cliente_elegido = _cliente_venta(request, f["cliente_campo"])
        if f["productos"].is_valid() & f["pagos"].is_valid():
            lineas = _lineas(f["productos"])
            try:
                total = _total_lineas(f["productos"])
                venta = servicios.vender_directo(lineas, _pagos_de_venta(f["pagos"], total), cliente=cliente_elegido)
            except (ValidationError, ReglaDeNegocioError) as error:
                _avisar_error(request, error)
            else:
                messages.success(request, f"Venta #{venta.id} registrada. Está en el Registro de ventas.")
                return redirect("web:venta_rapida")
    return render(request, "web/ventas/rapida.html", {
        **f, "oc": _opciones_cliente("cliente", elegido=cliente_elegido.pk if cliente_elegido else None),
    })


@login_required
@require_POST
def venta_rapida_resumen(request):
    f = _formularios_venta(request.POST)
    total = _total_lineas(f["productos"])
    pagos = [form.cleaned_data for form in f["pagos"].forms
             if form.is_valid() and form.cleaned_data and form.cleaned_data.get("metodo_pago")]
    escrito = sum(p["monto"] for p in pagos if p.get("monto"))
    sin_monto = [p for p in pagos if not p.get("monto")]
    # Igual que al guardar: un pago con el monto vacío se lleva lo que falta
    recargos = []
    for p in pagos:
        monto = p.get("monto") or (total - escrito if len(sin_monto) == 1 else 0)
        porcentaje = p["recargo_porcentaje"] if p.get("recargo_porcentaje") is not None else p["metodo_pago"].recargo_porcentaje
        if monto > 0 and porcentaje:
            recargo = Pago(monto=monto, recargo_porcentaje=porcentaje).recargo_monto     # misma cuenta que el pago
            recargos.append({"metodo": p["metodo_pago"].nombre, "porcentaje": porcentaje, "monto": recargo})
    asignado = total if len(sin_monto) == 1 and total > escrito else escrito
    total_recargos = sum((r["monto"] for r in recargos), 0)
    return render(request, "web/parciales/resumen_venta.html", {
        "total": total, "asignado": asignado, "falta": total - asignado, "varios_sin_monto": len(sin_monto) > 1,
        "recargos": recargos, "paga": total + total_recargos,
    })


# ---------- Devoluciones (paso 2: marcar que ya se devolvió) ----------

def _para_devolver(numero, linea_id=None):
    """Las reparaciones de una orden abierta, con cuánto se devolvería por cada una."""
    numero = str(numero or "").strip().lstrip("#")
    datos = {"numero": numero, "orden": None, "lineas": [], "linea_id": int(linea_id) if str(linea_id or "").isdigit() else None,
             "metodo_form": MetodoForm(prefix="dr")}
    if not numero.isdigit():
        return datos
    orden = OrdenTrabajo.objects.select_related("cliente", "venta").prefetch_related(*PREFETCH_ORDEN, "equipos__lineas_reparacion__reparacion").filter(pk=int(numero)).first()
    datos["orden"] = orden
    if orden is None or orden.cerrada:
        return datos
    devueltas = orden.lineas_devueltas
    for n, equipo in enumerate(orden.equipos.all(), start=1):
        for linea in equipo.lineas_reparacion.all():
            ya = linea.id in devueltas
            datos["lineas"].append({"linea": linea, "equipo": n, "devuelta": ya,
                                    "monto": None if ya else servicios.monto_para_devolver(linea)})
    return datos


@login_required
def reparaciones_para_devolver(request):
    """Devoluciones → "Devolver una reparación": al escribir el N° de orden (HTMX)."""
    return render(request, "web/parciales/reparaciones_devolver.html", {"dr": _para_devolver(request.GET.get("orden_buscar"))})


@login_required
def devoluciones(request):
    if request.method == "POST" and request.POST.get("accion") == "devolver_reparacion":
        linea = LineaReparacion.objects.filter(pk=_numero(request.POST.get("linea")) or 0).select_related("equipo", "reparacion").first()
        metodo_form = MetodoForm(request.POST, prefix="dr")
        metodo = metodo_form.cleaned_data["metodo_pago"] if metodo_form.is_valid() else None
        if linea is None:
            messages.error(request, "Elegí qué reparación se devuelve.")
        else:
            try:
                devolucion = servicios.devolver_reparacion(linea, metodo, request.POST.get("nota", "").strip())
            except (ValidationError, ReglaDeNegocioError) as error:
                _avisar_error(request, error)
            else:
                orden_id = linea.equipo.orden_trabajo_id
                if devolucion.devuelta:
                    messages.success(request, f"Orden #{orden_id}: se devolvió «{linea.reparacion}» ({pesos(devolucion.monto)}). Ya no se cobra.")
                else:
                    messages.success(request, f"Orden #{orden_id}: «{linea.reparacion}» ya no se cobra. Quedan {pesos(devolucion.monto)} "
                                              "para devolver (abajo, en «Por devolver»).")
                return redirect("web:devoluciones")
        return redirect(f"{reverse('web:devoluciones')}?orden={request.POST.get('orden', '')}#devolver-reparacion")

    if request.method == "POST" and request.POST.get("accion") == "anular":
        devolucion = get_object_or_404(Devolucion, pk=_numero(request.POST.get("devolucion")))
        try:
            servicios.anular_devolucion(devolucion)
        except ReglaDeNegocioError as error:
            _avisar_error(request, error)
        else:
            messages.success(request, f"Se anuló la devolución de la orden #{devolucion.orden_trabajo_id}.")
        return redirect("web:devoluciones")

    if request.method == "POST":
        devolucion = get_object_or_404(Devolucion, pk=_numero(request.POST.get("devolucion")))
        form = MetodoForm(request.POST, prefix=f"d{devolucion.id}")
        if form.is_valid():
            try:
                servicios.marcar_devuelta(devolucion, form.cleaned_data["metodo_pago"])
            except (ValidationError, ReglaDeNegocioError) as error:
                _avisar_error(request, error)
            else:
                messages.success(request, f"Devolución de la orden #{devolucion.orden_trabajo_id} marcada como hecha.")
                return redirect("web:devoluciones")
        else:
            messages.error(request, "Elegí con qué método se devolvió el dinero.")

    pendientes = (Devolucion.objects.filter(fecha_devolucion__isnull=True)
                  .select_related("orden_trabajo__cliente", "linea_reparacion__reparacion").order_by("fecha_registro"))
    filas = [(d, MetodoForm(prefix=f"d{d.id}")) for d in pendientes]
    hechas = (Devolucion.objects.filter(fecha_devolucion__isnull=False)
              .select_related("orden_trabajo__cliente", "metodo_pago").order_by("-fecha_devolucion")[:20])

    # Órdenes abiertas con plata a favor del cliente que todavía no tiene devolución registrada
    # (sin pagos no puede haber plata a favor: esas ni se cargan)
    abiertas = (OrdenTrabajo.objects.filter(venta__isnull=True, pagos__isnull=False).distinct()
                .select_related("cliente", "venta").prefetch_related(*PREFETCH_ORDEN).order_by("-id"))
    sin_registrar = []
    for orden in abiertas:
        falta_registrar = -orden.monto_adeudado - orden.monto_a_devolver
        if falta_registrar > 0:
            sin_registrar.append((orden, falta_registrar))

    return render(request, "web/devoluciones.html", {
        "filas": filas, "hechas": hechas, "sin_registrar": sin_registrar,
        # ?orden=12&linea=34 viene del botón "Devolver" de la orden
        "dr": _para_devolver(request.GET.get("orden"), request.GET.get("linea")),
    })


# ---------- Ventas ----------

PERIODOS = [
    ("hoy", "Hoy"),
    ("semana", "Últimos 7 días"),
    ("mes", "Este mes"),
    ("todas", "Todas"),
]


def _desde(periodo):
    """Fecha desde la que se cuentan las ventas del período (None = todas)."""
    hoy = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    if periodo == "hoy":
        return hoy
    if periodo == "semana":
        return hoy - timedelta(days=6)
    if periodo == "mes":
        return hoy.replace(day=1)
    return None


def _buscar_clientes(q):
    """Clientes por nombre, teléfono o email (sin repetidos, para usar con __in).
    El teléfono se compara solo con los dígitos: "3511234" encuentra "351-123 4"."""
    filtro = Q(nombre__icontains=q) | Q(telefonos__numero__icontains=q) | Q(email__icontains=q)
    digitos = "".join(ch for ch in q if ch.isdigit())
    if len(digitos) >= 3:
        filtro |= Q(pk__in=Telefono.objects.annotate(digitos=_solo_digitos("numero"))
                    .filter(digitos__contains=digitos).values("cliente_id"))
    return Cliente.objects.filter(filtro).values("pk")


# ---------- Elegir cliente (Nueva orden y Venta rápida) ----------
# Una lista con TODOS los clientes (A-Z) que se filtra mientras se escribe. Se manda de a
# partes: las siguientes se piden solas al llegar al final de la lista (así la pantalla
# carga rápido aunque haya miles). Nombre del campo -> texto de la opción "ninguno".
CAMPOS_CLIENTE = {"cli-cliente": None, "cliente": "Sin cliente"}
CLIENTES_POR_PARTE = 40


def _opciones_cliente(campo, q="", elegido=None, parte=1):
    elegido = int(elegido) if str(elegido or "").isdigit() else None
    q = q.strip()
    consulta = Cliente.objects.all()
    if q:
        consulta = consulta.filter(pk__in=_buscar_clientes(q))
    pagina = Paginator(consulta.prefetch_related("telefonos").order_by("nombre", "pk"), CLIENTES_POR_PARTE).get_page(parte)
    lista = list(pagina)
    # El elegido siempre se ve arriba (al volver con un error o al venir desde la ficha del cliente)
    if parte == 1 and elegido and all(c.pk != elegido for c in lista):
        actual = Cliente.objects.prefetch_related("telefonos").filter(pk=elegido).first()
        if actual:
            lista.insert(0, actual)
    return {"campo": campo, "q": q, "lista": lista, "elegido": elegido, "vacio": CAMPOS_CLIENTE[campo],
            "cantidad": pagina.paginator.count, "parte": parte,
            "siguiente": pagina.next_page_number() if pagina.has_next() else None}


@login_required
def buscar_clientes(request):
    """Resultados del buscador de clientes (HTMX): la lista entera o, con "parte", la continuación."""
    campo = request.GET.get("campo")
    if campo not in CAMPOS_CLIENTE:
        raise Http404
    parte = request.GET.get("parte", "1")
    oc = _opciones_cliente(campo, request.GET.get("buscar_cliente", ""), request.GET.get(campo),
                           int(parte) if parte.isdigit() else 1)
    plantilla = "opciones_cliente_mas.html" if oc["parte"] > 1 else "opciones_cliente.html"
    return render(request, f"web/parciales/{plantilla}", {"oc": oc})


def _solo_digitos(campo):
    expresion = F(campo)
    for signo in (" ", "-", ".", "(", ")", "+"):
        expresion = Replace(expresion, Value(signo), Value(""))
    return expresion


@login_required
def clientes_parecidos(request):
    """Al cargar un cliente nuevo: avisa si ya hay uno con ese teléfono o ese nombre (HTMX)."""
    nombre = request.GET.get("cli-nuevo_nombre", "").strip()
    telefono = "".join(ch for ch in request.GET.get("cli-nuevo_telefono", "") if ch.isdigit())
    filtro = Q()
    if len(telefono) >= 6:
        # Se comparan solo los dígitos (los números se cargan con espacios, guiones o puntos)
        filtro |= Q(pk__in=Telefono.objects.annotate(digitos=_solo_digitos("numero"))
                    .filter(digitos__contains=telefono[-8:]).values("cliente_id"))
    if len(nombre) >= 3:
        filtro |= Q(nombre__iexact=nombre)
    parecidos = list(Cliente.objects.filter(filtro).prefetch_related("telefonos")[:3]) if filtro else []
    return render(request, "web/parciales/clientes_parecidos.html", {"parecidos": parecidos})


@login_required
def ventas(request):
    periodo = request.GET.get("periodo", "mes")
    q = request.GET.get("q", "").strip()

    numero = _numero_buscado(q)
    consulta = Venta.objects.all()
    desde = _desde(periodo)
    if desde:
        consulta = consulta.filter(fecha__gte=desde)
    orden_lista = ("-id",)
    if q:
        por_cliente = Q(cliente__in=_buscar_clientes(q.lstrip("#") if numero is not None else q))
        # Igual que en órdenes: "#12" abre la venta; "12" solo si ningún cliente coincide
        if _abrir_directo(q, numero, Venta.objects.filter(pk=numero or 0).exists(),
                          numero is not None and Venta.objects.filter(por_cliente).exists()):
            return redirect("web:venta_detalle", numero=numero)
        if numero is not None:
            consulta = consulta.filter(por_cliente | Q(pk=numero))
            orden_lista = (Case(When(pk=numero, then=0), default=1), "-id")
        else:
            consulta = consulta.filter(por_cliente)
    totales = consulta.aggregate(total=Sum("total"), cantidad=Count("id"))

    lista = (consulta.select_related("cliente", "orden_trabajo")
             .prefetch_related("lineas_producto__producto", "orden_trabajo__equipos__modelo", "orden_trabajo__equipos__tipo",
                               "orden_trabajo__lineas_producto__producto", "pagos__metodo_pago", "orden_trabajo__pagos__metodo_pago",
                               "orden_trabajo__devoluciones__metodo_pago")
             .order_by(*orden_lista))
    pagina = Paginator(lista, 50).get_page(request.GET.get("pagina"))
    for venta in pagina:
        venta.cobro = _cobro_de(venta)
    return render(request, "web/ventas/lista.html", {
        "pagina": pagina, "periodos": PERIODOS, "periodo": periodo, "q": q,
        "total": totales["total"] or 0, "cantidad": totales["cantidad"], **_cobros_del_periodo(consulta),
    })


def _cobro_de(venta):
    """Con qué se cobró una venta y cuánto entró con recargo (en una orden: sus pagos menos lo devuelto)."""
    orden = venta.orden_trabajo if venta.orden_trabajo_id else None
    pagos = list(orden.pagos.all() if orden else venta.pagos.all())
    devuelto = sum((d.monto for d in orden.devoluciones.all() if d.devuelta), 0) if orden else 0
    metodos = list(dict.fromkeys(p.metodo_pago.nombre for p in pagos))
    cobrado = sum((p.total_cobrado for p in pagos), 0) - devuelto
    return {"metodos": metodos, "cobrado": cobrado, "con_recargo": cobrado != venta.total}


def _cobros_del_periodo(ventas):
    """Totales del registro: cobrado con recargos y cuánto entró por cada cuenta (efectivo / digital)."""
    pagos = (Pago.objects.filter(Q(venta__in=ventas) | Q(orden_trabajo__venta__in=ventas))
             .select_related("metodo_pago").only("monto", "recargo_porcentaje", "metodo_pago__cuenta"))
    devueltas = Devolucion.objects.filter(orden_trabajo__venta__in=ventas, fecha_devolucion__isnull=False).select_related("metodo_pago")
    por_cuenta = {"efectivo": 0, "digital": 0}
    cobrado = 0
    for pago in pagos:
        cobrado += pago.total_cobrado
        por_cuenta[pago.metodo_pago.cuenta] = por_cuenta.get(pago.metodo_pago.cuenta, 0) + pago.total_cobrado
    for devolucion in devueltas:
        cobrado -= devolucion.monto
        por_cuenta[devolucion.metodo_pago.cuenta] = por_cuenta.get(devolucion.metodo_pago.cuenta, 0) - devolucion.monto
    return {"cobrado": cobrado, "efectivo": por_cuenta["efectivo"], "digital": por_cuenta["digital"]}


@login_required
def venta_detalle(request, numero):
    venta = get_object_or_404(
        Venta.objects.select_related("cliente", "orden_trabajo").prefetch_related(
            "lineas_producto__producto", "pagos__metodo_pago", "cliente__telefonos"),
        pk=numero)
    if request.method == "POST" and request.POST.get("accion") == "anular_venta":
        try:
            servicios.anular_venta_directa(venta)
        except ReglaDeNegocioError as error:
            _avisar_error(request, error)
            return redirect("web:venta_detalle", numero=numero)
        messages.success(request, f"Se anuló la venta #{numero}.")
        return redirect("web:ventas")
    orden = _orden_para_mostrar(venta.orden_trabajo_id) if venta.orden_trabajo_id else None
    pagos = orden.pagos.all() if orden else venta.pagos.all()
    return render(request, "web/ventas/detalle.html", {
        "venta": venta, "orden": orden, "pagos": pagos,
        "total_cobrado": sum((p.total_cobrado for p in pagos), 0),
    })


# ---------- Clientes ----------

@login_required
def lista_clientes(request):
    q = request.GET.get("q", "").strip()
    consulta = Cliente.objects.all()
    if q:
        consulta = consulta.filter(pk__in=_buscar_clientes(q))
    consulta = (consulta.annotate(cant_ordenes=Count("ordenes", distinct=True),
                                  ultima_orden=Max("ordenes__fecha_recepcion"))
                .prefetch_related("telefonos").order_by("nombre"))
    pagina = Paginator(consulta, 50).get_page(request.GET.get("pagina"))
    return render(request, "web/clientes/lista.html", {"pagina": pagina, "q": q})


@login_required
def cliente_nuevo(request):
    form = ClienteNuevoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cliente = servicios.crear_cliente(form.save(commit=False), form.cleaned_data["telefono"])
        except (ValidationError, ReglaDeNegocioError) as error:
            _avisar_error(request, error)
        else:
            messages.success(request, f"Cliente {cliente.nombre} creado.")
            if request.POST.get("despues") == "orden":
                return redirect(f"{reverse('web:orden_nueva')}?cliente={cliente.id}")
            return redirect("web:cliente_detalle", numero=cliente.id)
    return render(request, "web/clientes/nuevo.html", {"form": form})


def _accion_cliente(request, cliente, accion, f):
    """Ejecuta la acción enviada desde la ficha. Devuelve el mensaje de éxito,
    o None si el formulario tiene errores (se vuelven a mostrar)."""
    post = request.POST
    if accion == "datos":
        if not f["datos_form"].is_valid():
            return None
        f["datos_form"].save()
        return "Datos guardados."
    if accion == "telefono":
        if not f["telefono_form"].is_valid():
            return None
        datos = f["telefono_form"].cleaned_data
        servicios.agregar_telefono(cliente, datos["numero"], datos["principal"])
        return "Teléfono agregado."
    if accion in ("principal", "quitar_telefono"):
        telefono = get_object_or_404(Telefono, pk=_numero(post.get("telefono")), cliente=cliente)
        if accion == "principal":
            servicios.marcar_telefono_principal(telefono)
            return f"{telefono.numero} es ahora el teléfono principal."
        servicios.quitar_telefono(telefono)
        return "Teléfono quitado."
    raise ReglaDeNegocioError("Acción desconocida.")


@login_required
def cliente_detalle(request, numero):
    cliente = get_object_or_404(Cliente, pk=numero)
    if request.method == "POST" and request.POST.get("accion") == "eliminar_cliente":
        try:
            servicios.eliminar_cliente(cliente)
        except ReglaDeNegocioError as error:
            _avisar_error(request, error)
            return redirect("web:cliente_detalle", numero=numero)
        messages.success(request, f"Se eliminó el cliente {cliente.nombre}.")
        return redirect("web:clientes")
    accion = request.POST.get("accion") if request.method == "POST" else None
    datos = request.POST if accion else None
    f = {
        "datos_form": ClienteForm(datos if accion == "datos" else None, instance=cliente, prefix="cli"),
        "telefono_form": TelefonoForm(datos if accion == "telefono" else None, prefix="tel"),
    }
    if accion:
        try:
            with transaction.atomic():
                exito = _accion_cliente(request, cliente, accion, f)
        except (ValidationError, ReglaDeNegocioError) as error:
            _avisar_error(request, error)
        else:
            if exito:
                messages.success(request, exito)
                return redirect("web:cliente_detalle", numero=cliente.id)
        if accion != "datos":
            cliente.refresh_from_db()      # el formulario con errores no debe cambiar el título

    ordenes_cliente = list(cliente.ordenes.select_related("venta").prefetch_related(*PREFETCH_ORDEN).order_by("-id"))
    abiertas = [o for o in ordenes_cliente if not o.cerrada]
    return render(request, "web/clientes/detalle.html", {
        "cliente": cliente,
        "telefonos": cliente.telefonos.order_by("-principal", "id"),
        "ordenes": ordenes_cliente,
        "compras": cliente.ventas_cliente.filter(orden_trabajo__isnull=True)
                          .prefetch_related("lineas_producto__producto").order_by("-id"),
        "en_curso": sum(1 for o in abiertas if o.estado in EN_CURSO),
        "debe": sum((o.monto_adeudado for o in abiertas if o.monto_adeudado > 0), 0),
        "a_favor": sum((-o.monto_adeudado for o in abiertas if o.monto_adeudado < 0), 0),
        **f,
    })


# ---------- Productos ----------

ESTADOS_PRODUCTO = [("activos", "Activos"), ("inactivos", "Desactivados"), ("todos", "Todos")]


@login_required
def productos(request):
    estado = request.GET.get("estado", "activos")
    categoria = request.GET.get("categoria", "")
    q = request.GET.get("q", "").strip()

    consulta = Producto.objects.select_related("categoria", "marca").order_by("nombre")
    if estado == "activos":
        consulta = consulta.filter(activo=True)
    elif estado == "inactivos":
        consulta = consulta.filter(activo=False)
    if categoria.isdigit():
        consulta = consulta.filter(categoria_id=int(categoria))
    if q:
        consulta = consulta.filter(Q(nombre__icontains=q) | Q(marca__nombre__icontains=q))

    pagina = Paginator(consulta, 50).get_page(request.GET.get("pagina"))
    return render(request, "web/productos/lista.html", {
        "pagina": pagina, "estados": ESTADOS_PRODUCTO, "estado": estado, "q": q,
        "categoria": int(categoria) if categoria.isdigit() else None,
        "categorias": CategoriaProducto.objects.order_by("-activa", "nombre"),
    })


def _ultimos_movimientos(producto, cuantos=10):
    """Las últimas veces que se vendió, en ventas directas y en órdenes, de la más nueva a la más vieja."""
    directas = [(l.venta.fecha, l, l.venta, None) for l in
                producto.lineaproductoventas.select_related("venta").order_by("-venta__fecha")[:cuantos]]
    en_ordenes = [(l.orden_trabajo.fecha_recepcion, l, None, l.orden_trabajo) for l in
                  producto.lineaproductoordens.select_related("orden_trabajo").order_by("-orden_trabajo__fecha_recepcion")[:cuantos]]
    return sorted(directas + en_ordenes, key=lambda m: m[0], reverse=True)[:cuantos]


def _pantalla_producto(request, producto):
    form = ProductoForm(request.POST if request.method == "POST" else None, instance=producto)
    if request.method == "POST":
        if request.POST.get("accion") == "eliminar" and producto.pk:
            try:
                producto.delete()
            except ProtectedError:
                messages.error(request, f"{producto.nombre} ya se vendió o está en una orden: no se puede eliminar sin "
                                        "perder ese historial. Desactivalo: deja de aparecer al vender.")
                return redirect("web:producto_detalle", numero=producto.pk)
            messages.success(request, f"Se eliminó {producto.nombre}.")
            return redirect("web:productos")
        if request.POST.get("accion") in ("activar", "desactivar") and producto.pk:
            producto.activo = request.POST["accion"] == "activar"
            producto.save(update_fields=["activo"])
            messages.success(request, f"{producto.nombre}: {'activado' if producto.activo else 'desactivado'}.")
            return redirect("web:producto_detalle", numero=producto.pk)
        if form.is_valid():
            nuevo = producto.pk is None
            producto = form.save()
            messages.success(request, f"Producto {producto.nombre} {'creado' if nuevo else 'guardado'}.")
            if nuevo and request.POST.get("despues") == "otro":
                return redirect("web:producto_nuevo")
            return redirect("web:producto_detalle", numero=producto.pk)
        producto = Producto.objects.get(pk=producto.pk) if producto.pk else producto   # el título no cambia con errores
    return render(request, "web/productos/form.html", {
        "producto": producto, "form": form,
        "movimientos": _ultimos_movimientos(producto) if producto.pk else [],
        "margen": _margen(form, producto),
    })


@login_required
def producto_nuevo(request):
    return _pantalla_producto(request, Producto())


@login_required
def producto_detalle(request, numero):
    return _pantalla_producto(request, get_object_or_404(Producto, pk=numero))


def _margen(form, producto):
    """Margen y ganancia por unidad con los precios del formulario (o los guardados).
    El margen se calcula con la misma cuenta del modelo (Producto.margen)."""
    calculo = Producto(precio_compra=producto.precio_compra, precio_venta=producto.precio_venta)
    if form.is_bound:
        for campo in ("precio_compra", "precio_venta"):
            try:
                setattr(calculo, campo, form.fields[campo].clean(form.data.get(campo)))
            except ValidationError:
                setattr(calculo, campo, None)
    if calculo.precio_compra is None or calculo.precio_venta is None:
        return None
    return {"porcentaje": calculo.margen, "ganancia": calculo.precio_venta - calculo.precio_compra}


@login_required
@require_POST
def producto_margen(request):
    """Margen en vivo (HTMX) mientras se escriben los precios."""
    return render(request, "web/parciales/margen.html", {"margen": _margen(ProductoForm(request.POST), Producto())})
