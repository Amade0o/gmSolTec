"""Catálogo: las tablas chicas que el dueño mantiene (categorías, marcas, modelos,
reparaciones, métodos de pago). Una sola pantalla con una pestaña por tabla.

Desactivar: deja de aparecer en los desplegables y lo viejo lo sigue mostrando.
Eliminar: solo si nunca se usó (si ya está en una orden, producto o venta, la base no lo deja
borrar y se ofrece desactivarlo).

alta_rapida: el "+ Nuevo" de los desplegables. Carga una marca, categoría, modelo o reparación
sin salir de la pantalla (diálogo con HTMX) y la deja elegida.
"""
import json

from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from negocio.models import CategoriaProducto, CategoriaReparacion, Marca, MetodoPago, ModeloEquipo, Reparacion, TipoEquipo

from .forms import (
    CategoriaProductoForm, CategoriaReparacionForm, MarcaForm, MetodoPagoForm, ModeloEquipoForm, ModeloRapidoForm,
    ReparacionForm, ReparacionRapidaForm, TipoEquipoForm,
)


def _recargo(m):
    return f"{m.recargo_porcentaje.normalize():f} %" if m.recargo_porcentaje else "—"


# Cada pestaña: grupo, título, nombre en singular (para los textos: "Agregar marca"), tabla,
# formulario, campo "activo", columnas (título, cómo se muestra) y búsqueda.
SECCIONES = {
    "tipos-equipo": {
        "grupo": "Equipos", "titulo": "Tipos de equipo", "singular": "tipo de equipo", "modelo": TipoEquipo,
        "form": TipoEquipoForm, "activo": "activo", "columnas": [], "buscar": ["nombre"],
        "ayuda": "Celular, Notebook, PC… Se elige al recibir un equipo y en cada modelo.",
    },
    "marcas": {
        "grupo": "Equipos", "titulo": "Marcas", "singular": "marca", "modelo": Marca, "form": MarcaForm,
        "activo": "activa", "columnas": [], "buscar": ["nombre"],
        "ayuda": "Se usan en los modelos de equipo y en los productos.",
    },
    "modelos": {
        "grupo": "Equipos", "titulo": "Modelos de equipo", "singular": "modelo de equipo", "modelo": ModeloEquipo,
        "form": ModeloEquipoForm, "activo": "activo", "relacion": ("marca", "tipo"), "orden": ("marca__nombre", "nombre"),
        "columnas": [("Marca", lambda m: m.marca.nombre), ("Tipo", lambda m: m.tipo.nombre)],
        "buscar": ["nombre", "marca__nombre"],
        "ayuda": "El modelo del equipo que se repara (por ejemplo Samsung Galaxy A14). La PC puede ir sin modelo.",
    },
    "categorias-reparacion": {
        "grupo": "Reparaciones", "titulo": "Categorías de reparación", "singular": "categoría de reparación",
        "modelo": CategoriaReparacion, "form": CategoriaReparacionForm, "activo": "activo",
        "columnas": [], "buscar": ["nombre"],
        "ayuda": "Agrupan las reparaciones para las estadísticas (por ejemplo: Pantalla, Batería, Software).",
    },
    "reparaciones": {
        "grupo": "Reparaciones", "titulo": "Reparaciones", "singular": "reparación", "modelo": Reparacion,
        "form": ReparacionForm, "activo": "activo", "relacion": "categoria", "orden": ("categoria__nombre", "nombre"),
        "columnas": [("Categoría", lambda r: r.categoria.nombre)], "buscar": ["nombre", "categoria__nombre"],
        "ayuda": "Los tipos de reparación que se eligen en la orden. El precio no va acá: se pone en cada orden.",
    },
    "categorias-producto": {
        "grupo": "Productos", "titulo": "Categorías de producto", "singular": "categoría de producto",
        "modelo": CategoriaProducto, "form": CategoriaProductoForm, "activo": "activa",
        "columnas": [], "buscar": ["nombre"],
        "ayuda": "Cables, Cargadores, Fundas… Los productos se cargan en el menú Productos.",
    },
    "metodos-pago": {
        "grupo": "Pagos", "titulo": "Métodos de pago", "singular": "método de pago", "modelo": MetodoPago,
        "form": MetodoPagoForm, "activo": "activo",
        "columnas": [("Cuenta", lambda m: m.get_cuenta_display()), ("Recargo", _recargo)], "buscar": ["nombre"],
        "ayuda": "Efectivo, Débito, Crédito… El recargo se sugiere solo al cobrar y se puede cambiar en cada pago.",
    },
}


def _grupos():
    """[(grupo, [(clave, título), …]), …] para las pestañas."""
    grupos = {}
    for clave, sec in SECCIONES.items():
        grupos.setdefault(sec["grupo"], []).append((clave, sec["titulo"]))
    return list(grupos.items())


def _seccion(clave):
    if clave not in SECCIONES:
        raise Http404("Sección del catálogo desconocida.")
    return {"clave": clave, **SECCIONES[clave]}


def _filas(sec, consulta):
    # Cada valor va con el título de su columna (en el celular la tabla pasa a tarjetas y lo muestra)
    return [(obj, [(titulo, mostrar(obj)) for titulo, mostrar in sec["columnas"]], getattr(obj, sec["activo"])) for obj in consulta]


@login_required
def catalogo(request, seccion="tipos-equipo"):
    sec = _seccion(seccion)
    form = sec["form"](request.POST or None, prefix="nuevo")
    if request.method == "POST" and form.is_valid():
        nuevo = form.save()
        messages.success(request, f"Se agregó {sec['singular']}: “{nuevo.nombre}”.")
        return redirect("web:catalogo", seccion=seccion)

    estado = request.GET.get("estado", "activos")
    q = request.GET.get("q", "").strip()
    consulta = sec["modelo"].objects.order_by(*sec.get("orden", ("nombre",)))
    if sec.get("relacion"):
        relacion = sec["relacion"]
        consulta = consulta.select_related(*((relacion,) if isinstance(relacion, str) else relacion))
    if estado == "activos":
        consulta = consulta.filter(**{sec["activo"]: True})
    if q:
        filtro = Q()
        for campo in sec["buscar"]:
            filtro |= Q(**{f"{campo}__icontains": q})
        consulta = consulta.filter(filtro)

    return render(request, "web/catalogo/seccion.html", {
        "sec": sec, "grupos": _grupos(),
        "form": form, "filas": _filas(sec, consulta), "estado": estado, "q": q,
    })


@login_required
def catalogo_editar(request, seccion, numero):
    sec = _seccion(seccion)
    obj = get_object_or_404(sec["modelo"], pk=numero)
    if request.method == "POST" and request.POST.get("accion") == "eliminar":
        try:
            obj.delete()
        except ProtectedError:
            messages.error(request, f"“{obj.nombre}” ya se usó (en órdenes, productos o ventas): no se puede eliminar "
                                    "sin perder ese historial. Desactivalo: deja de aparecer al cargar cosas nuevas.")
            return redirect("web:catalogo_editar", seccion=seccion, numero=obj.pk)
        messages.success(request, f"Se eliminó “{obj.nombre}”.")
        return redirect("web:catalogo", seccion=seccion)
    if request.method == "POST" and request.POST.get("accion") in ("activar", "desactivar"):
        setattr(obj, sec["activo"], request.POST["accion"] == "activar")
        obj.save(update_fields=[sec["activo"]])
        messages.success(request, f"“{obj.nombre}”: {'activo' if request.POST['accion'] == 'activar' else 'desactivado'}.")
        return redirect("web:catalogo_editar", seccion=seccion, numero=obj.pk)

    form = sec["form"](request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Cambios guardados.")
        return redirect("web:catalogo", seccion=seccion)
    if form.is_bound:
        obj = sec["modelo"].objects.get(pk=obj.pk)      # el título no cambia con errores
    return render(request, "web/catalogo/editar.html", {
        "sec": sec, "obj": obj, "form": form, "activo": getattr(obj, sec["activo"]),
    })


# ---------- "+ Nuevo" desde otra pantalla ----------

ALTA_RAPIDA = {
    # sección: (título del diálogo, formulario)
    "tipos-equipo": ("Nuevo tipo de equipo", TipoEquipoForm),
    "categorias-producto": ("Nueva categoría de producto", CategoriaProductoForm),
    "marcas": ("Nueva marca", MarcaForm),
    "modelos": ("Nuevo modelo de equipo", ModeloRapidoForm),
    "categorias-reparacion": ("Nueva categoría de reparación", CategoriaReparacionForm),
    "reparaciones": ("Nueva reparación", ReparacionRapidaForm),
}


def _ya_existe(seccion, form):
    """Si lo que se quiso agregar ya está cargado (mismo nombre), se usa ese en vez de dar error."""
    nombre = (form.data.get(form.add_prefix("nombre")) or "").strip()
    datos = getattr(form, "cleaned_data", {})
    filtro = {"nombre__iexact": nombre}
    if seccion == "modelos":
        filtro["marca"] = datos.get("marca")
    if seccion == "reparaciones":
        filtro["categoria"] = datos.get("categoria")
    if not nombre or None in filtro.values():
        return None
    return SECCIONES[seccion]["modelo"].objects.filter(**filtro).first()


def _texto_opcion(seccion, obj):
    """Igual que en los desplegables de las pantallas."""
    return f"{obj.marca} {obj.nombre}" if seccion == "modelos" else obj.nombre


@login_required
def alta_rapida(request, seccion):
    if seccion not in ALTA_RAPIDA:
        raise Http404("No se puede agregar desde acá.")
    titulo, Formulario = ALTA_RAPIDA[seccion]
    destino = request.GET.get("destino") or request.POST.get("destino", "")
    if request.method == "POST":
        with transaction.atomic():
            form = Formulario(request.POST, prefix="rapido")
            valido = form.is_valid()
            # Si ya existe con ese nombre (sin importar mayúsculas) se elige ese: no se duplica
            obj = _ya_existe(seccion, form)
            if obj is None and valido:
                obj = form.save()
            if obj is not None and not getattr(obj, SECCIONES[seccion]["activo"]):
                form.add_error(None, f"«{_texto_opcion(seccion, obj)}» ya existe pero está desactivado: activalo en Configuración.")
                obj = None
            if obj is not None:
                respuesta = render(request, "web/catalogo/rapido_ok.html", {"obj": obj})
                # app.js agrega la opción a los desplegables y la deja elegida en "destino"
                respuesta["HX-Trigger"] = json.dumps({"catalogo-agregado": {
                    "seccion": seccion, "id": obj.pk, "texto": _texto_opcion(seccion, obj), "destino": destino}})
                return respuesta
            transaction.set_rollback(True)      # si se creó una marca o categoría nueva, se deshace
    else:
        form = Formulario(prefix="rapido")
    return render(request, "web/catalogo/rapido.html", {
        "titulo": titulo, "form": form, "seccion": seccion, "destino": destino,
        "boton": f"Agregar {SECCIONES[seccion]['singular']}",
        "ayuda": SECCIONES[seccion].get("ayuda", ""),
    })
