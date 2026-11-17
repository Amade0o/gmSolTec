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

from catalogo.models import CategoriaProducto, CategoriaReparacion, Marca, MetodoPago, ModeloEquipo, Reparacion

from .forms import (
    CategoriaProductoForm, CategoriaReparacionForm, MarcaForm, MetodoPagoForm, ModeloEquipoForm, ModeloRapidoForm,
    ReparacionForm, ReparacionRapidaForm,
)


def _recargo(m):
    return f"{m.recargo_porcentaje.normalize():f} %" if m.recargo_porcentaje else "—"


# Cada pestaña: tabla, formulario, campo "activo", columnas (título, cómo se muestra) y búsqueda
SECCIONES = {
    "categorias-producto": {
        "titulo": "Categorías de producto", "modelo": CategoriaProducto,
        "form": CategoriaProductoForm, "activo": "activa",
        "columnas": [], "buscar": ["nombre"],
    },
    "marcas": {
        "titulo": "Marcas", "modelo": Marca, "form": MarcaForm, "activo": "activa",
        "columnas": [], "buscar": ["nombre"],
        "ayuda": "Se usan en los productos y en los modelos de equipo.",
    },
    "modelos": {
        "titulo": "Modelos de equipo", "modelo": ModeloEquipo, "form": ModeloEquipoForm,
        "activo": "activo", "relacion": "marca", "orden": ("marca__nombre", "nombre"),
        "columnas": [("Marca", lambda m: m.marca.nombre), ("Tipo", lambda m: m.get_tipo_display())],
        "buscar": ["nombre", "marca__nombre"],
        "ayuda": "El modelo del equipo que se repara. La PC no lleva modelo.",
    },
    "categorias-reparacion": {
        "titulo": "Categorías de reparación", "modelo": CategoriaReparacion,
        "form": CategoriaReparacionForm, "activo": "activo", "columnas": [], "buscar": ["nombre"],
    },
    "reparaciones": {
        "titulo": "Reparaciones", "modelo": Reparacion, "form": ReparacionForm,
        "activo": "activo", "relacion": "categoria", "orden": ("categoria__nombre", "nombre"),
        "columnas": [("Categoría", lambda r: r.categoria.nombre)], "buscar": ["nombre", "categoria__nombre"],
        "ayuda": "El precio de cada reparación se pone en la orden, no acá.",
    },
    "metodos-pago": {
        "titulo": "Métodos de pago", "modelo": MetodoPago, "form": MetodoPagoForm,
        "activo": "activo",
        "columnas": [("Cuenta", lambda m: m.get_cuenta_display()), ("Recargo", _recargo)], "buscar": ["nombre"],
    },
}


def _seccion(clave):
    if clave not in SECCIONES:
        raise Http404("Sección del catálogo desconocida.")
    return {"clave": clave, **SECCIONES[clave]}


def _filas(sec, consulta):
    # Cada valor va con el título de su columna (en el celular la tabla pasa a tarjetas y lo muestra)
    return [(obj, [(titulo, mostrar(obj)) for titulo, mostrar in sec["columnas"]], getattr(obj, sec["activo"])) for obj in consulta]


@login_required
def catalogo(request, seccion="categorias-producto"):
    sec = _seccion(seccion)
    form = sec["form"](request.POST or None, prefix="nuevo")
    if request.method == "POST" and form.is_valid():
        nuevo = form.save()
        messages.success(request, f"Se agregó “{nuevo.nombre}”.")
        return redirect("web:catalogo", seccion=seccion)

    estado = request.GET.get("estado", "activos")
    q = request.GET.get("q", "").strip()
    consulta = sec["modelo"].objects.order_by(*sec.get("orden", ("nombre",)))
    if sec.get("relacion"):
        consulta = consulta.select_related(sec["relacion"])
    if estado == "activos":
        consulta = consulta.filter(**{sec["activo"]: True})
    if q:
        filtro = Q()
        for campo in sec["buscar"]:
            filtro |= Q(**{f"{campo}__icontains": q})
        consulta = consulta.filter(filtro)

    return render(request, "web/catalogo/seccion.html", {
        "sec": sec, "secciones": [(c, s["titulo"]) for c, s in SECCIONES.items()],
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
                form.add_error(None, f"«{_texto_opcion(seccion, obj)}» ya existe pero está desactivado: activalo en el Catálogo.")
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
        "ayuda": SECCIONES[seccion].get("ayuda", ""),
    })
