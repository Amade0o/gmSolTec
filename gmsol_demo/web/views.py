"""Vistas de la interfaz propia.

Las vistas no tienen reglas de negocio: leen los formularios, llaman a
catalogo/servicios.py y muestran el resultado. Después de guardar algo se
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
from django.db.models import Count, Max, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalogo import servicios
from catalogo.models import (
    EQUIPO_ORDEN_ESTADO_CHOICES, Cliente, Devolucion, EquipoRecibido, LineaProductoOrden,
    CategoriaProducto, LineaReparacion, OrdenTrabajo, Pago, Producto, Reparacion,
    Telefono, Venta,
)
from catalogo.servicios import ReglaDeNegocioError

from .forms import (
    ClienteForm, ClienteNuevoForm, ClienteOrdenForm, DevolucionForm, ElegirCliente, EntregaForm, EquipoForm, LineaProductoForm,
    LineaReparacionForm, MetodoForm, PagoForm, PagosVentaFormSet, ProductosFormSet,
    ProductoForm, ProductosVentaFormSet, ReparacionesFormSet, TelefonoForm, clientes,
)

# Lo que hace falta para calcular estado, total y saldo sin una consulta por orden
PREFETCH_ORDEN = ("equipos__modelo", "equipos__lineas_reparacion", "lineas_producto", "pagos", "devoluciones")
EN_CURSO = ("pendiente", "lista", "no_arreglable")


def _mensajes_de(error):
    """Convierte un error de las reglas en una lista de textos para mostrar."""
    if isinstance(error, ValidationError):
        return error.messages
    return [str(error)]


def _avisar_error(request, error):
    for texto in _mensajes_de(error):
        messages.error(request, texto)


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
        "listas": sum(1 for o in en_curso if o.estado == "lista"),
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
    ("finalizada", "Finalizadas sin venta"),
    ("todas", "Todas"),
]


@login_required
def ordenes(request):
    filtro = request.GET.get("estado", "curso")
    q = request.GET.get("q", "").strip()

    # "#12" o "12": si existe esa orden, se abre directo
    numero = q.lstrip("#")
    if numero.isdigit() and len(numero) <= 6 and OrdenTrabajo.objects.filter(pk=int(numero)).exists():
        return redirect("web:orden_detalle", numero=int(numero))

    consulta = (OrdenTrabajo.objects.select_related("cliente", "venta")
                .prefetch_related(*PREFETCH_ORDEN).order_by("-id"))
    if q:
        consulta = consulta.filter(
            Q(cliente__nombre__icontains=q) | Q(cliente__telefonos__numero__icontains=q)).distinct()
    if filtro == "cerrada":
        consulta = consulta.filter(venta__isnull=False)
    elif filtro != "todas":
        consulta = consulta.filter(venta__isnull=True)

    # El estado se calcula (no está en la base), por eso se filtra acá
    lista = list(consulta)
    if filtro == "curso":
        lista = [o for o in lista if o.estado in EN_CURSO]
    elif filtro in ("pendiente", "lista", "no_arreglable", "finalizada"):
        lista = [o for o in lista if o.estado == filtro]

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
    else:
        cliente = request.GET.get("cliente", "")
        f = _formularios_nueva_orden(cliente=int(cliente) if cliente.isdigit() else None)
    return render(request, "web/ordenes/nueva.html", f)


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
            "equipos__modelo__marca", "equipos__lineas_reparacion__reparacion",
            "lineas_producto__producto", "pagos__metodo_pago", "devoluciones__metodo_pago",
            "devoluciones__linea_reparacion__reparacion", "cliente__telefonos"),
        pk=numero)


def _formularios_detalle(orden, datos=None, accion=None):
    """Los formularios chicos del detalle. Solo el de la acción enviada recibe los datos."""
    def con_datos(nombre):
        return datos if accion == nombre else None
    return {
        "reparacion_form": LineaReparacionForm(con_datos("reparacion"), prefix="rep"),
        "reparacion_vacio": LineaReparacionForm(prefix="rep"),     # para los otros equipos
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
        equipo = get_object_or_404(EquipoRecibido, pk=post.get("equipo"), orden_trabajo=orden)
        servicios.cambiar_estado_equipo(equipo, post.get("estado"))
        return f"Equipo {equipo.id}: {equipo.get_estado_display()}."
    if accion == "reparacion":
        equipo = get_object_or_404(EquipoRecibido, pk=post.get("equipo"), orden_trabajo=orden)
        if not f["reparacion_form"].is_valid():
            return None
        servicios.agregar_reparacion(equipo, f["reparacion_form"].save(commit=False))
        return "Reparación agregada."
    if accion == "quitar_reparacion":
        linea = get_object_or_404(LineaReparacion, pk=post.get("linea"), equipo__orden_trabajo=orden)
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
        linea = get_object_or_404(LineaProductoOrden, pk=post.get("linea"), orden_trabajo=orden)
        servicios.quitar_producto(linea)
        return "Producto quitado."
    if accion == "pago":
        if not f["pago_form"].is_valid():
            return None
        datos = f["pago_form"].cleaned_data
        servicios.agregar_pago(orden, datos["metodo_pago"], datos["monto"], datos["recargo_porcentaje"])
        return "Pago registrado."
    if accion == "devolucion":
        if not f["devolucion_form"].is_valid():
            return None
        datos = f["devolucion_form"].cleaned_data
        servicios.registrar_devolucion(orden, datos["monto"], datos["linea_reparacion"], datos["nota"])
        return "Devolución registrada: queda pendiente de hacer en Devoluciones."
    raise ReglaDeNegocioError("Acción desconocida.")


@login_required
def orden_detalle(request, numero):
    f = None
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
    return render(request, "web/ordenes/detalle.html", {
        "orden": orden, "estados_equipo": EQUIPO_ORDEN_ESTADO_CHOICES, **f,
    })


# ---------- 7.5 Entregar ----------

@login_required
def entregar(request):
    """Órdenes listas para entregar (y búsqueda entre las abiertas)."""
    q = request.GET.get("q", "").strip()
    consulta = (OrdenTrabajo.objects.filter(venta__isnull=True).select_related("cliente")
                .prefetch_related(*PREFETCH_ORDEN).order_by("-id"))
    if q:
        numero = q.lstrip("#")
        filtro = Q(cliente__nombre__icontains=q) | Q(cliente__telefonos__numero__icontains=q)
        if numero.isdigit():
            filtro |= Q(pk=int(numero))
        consulta = consulta.filter(filtro).distinct()
        lista = [o for o in consulta if o.estado in EN_CURSO]
    else:
        lista = [o for o in consulta if o.estado == "lista"]
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
            messages.success(request, f"Orden #{orden.id} entregada. Venta #{venta.id} registrada.")
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
                messages.success(request, f"Venta #{venta.id} registrada.")
                return redirect("web:venta_rapida")
    return render(request, "web/ventas/rapida.html", {
        **f, "clientes": clientes(), "cliente_elegido": cliente_elegido,
    })


@login_required
@require_POST
def venta_rapida_resumen(request):
    f = _formularios_venta(request.POST)
    total = _total_lineas(f["productos"])
    asignado = 0
    for form in f["pagos"].forms:
        if form.is_valid() and form.cleaned_data and form.cleaned_data.get("monto"):
            asignado += form.cleaned_data["monto"]
    return render(request, "web/parciales/resumen_venta.html", {
        "total": total, "asignado": asignado, "falta": total - asignado,
    })


# ---------- Devoluciones (paso 2: marcar que ya se devolvió) ----------

@login_required
def devoluciones(request):
    if request.method == "POST":
        devolucion = get_object_or_404(Devolucion, pk=request.POST.get("devolucion"))
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
    abiertas = (OrdenTrabajo.objects.filter(venta__isnull=True).select_related("cliente")
                .prefetch_related(*PREFETCH_ORDEN).order_by("-id"))
    sin_registrar = []
    for orden in abiertas:
        falta_registrar = -orden.monto_adeudado - orden.monto_a_devolver
        if falta_registrar > 0:
            sin_registrar.append((orden, falta_registrar))

    return render(request, "web/devoluciones.html", {
        "filas": filas, "hechas": hechas, "sin_registrar": sin_registrar,
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
    """Clientes por nombre, teléfono o email (sin repetidos, para usar con __in)."""
    return Cliente.objects.filter(
        Q(nombre__icontains=q) | Q(telefonos__numero__icontains=q) | Q(email__icontains=q)).values("pk")


@login_required
def ventas(request):
    periodo = request.GET.get("periodo", "mes")
    q = request.GET.get("q", "").strip()

    # "#12" o "12": si existe esa venta, se abre directo
    numero = q.lstrip("#")
    if numero.isdigit() and len(numero) <= 6 and Venta.objects.filter(pk=int(numero)).exists():
        return redirect("web:venta_detalle", numero=int(numero))

    consulta = Venta.objects.all()
    desde = _desde(periodo)
    if desde:
        consulta = consulta.filter(fecha__gte=desde)
    if q:
        consulta = consulta.filter(cliente__in=_buscar_clientes(q))
    totales = consulta.aggregate(total=Sum("total"), cantidad=Count("id"))

    lista = (consulta.select_related("cliente", "orden_trabajo")
             .prefetch_related("lineas_producto__producto", "orden_trabajo__equipos__modelo")
             .order_by("-id"))
    pagina = Paginator(lista, 50).get_page(request.GET.get("pagina"))
    return render(request, "web/ventas/lista.html", {
        "pagina": pagina, "periodos": PERIODOS, "periodo": periodo, "q": q,
        "total": totales["total"] or 0, "cantidad": totales["cantidad"],
    })


@login_required
def venta_detalle(request, numero):
    venta = get_object_or_404(
        Venta.objects.select_related("cliente", "orden_trabajo").prefetch_related(
            "lineas_producto__producto", "pagos__metodo_pago", "cliente__telefonos"),
        pk=numero)
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
        telefono = get_object_or_404(Telefono, pk=post.get("telefono"), cliente=cliente)
        if accion == "principal":
            servicios.marcar_telefono_principal(telefono)
            return f"{telefono.numero} es ahora el teléfono principal."
        servicios.quitar_telefono(telefono)
        return "Teléfono quitado."
    raise ReglaDeNegocioError("Acción desconocida.")


@login_required
def cliente_detalle(request, numero):
    cliente = get_object_or_404(Cliente, pk=numero)
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
