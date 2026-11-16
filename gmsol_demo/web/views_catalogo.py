"""Catálogo: las tablas chicas que el dueño mantiene (categorías, marcas, modelos,
reparaciones, métodos de pago). Una sola pantalla con una pestaña por tabla.

Nada se borra: se desactiva (deja de aparecer en los desplegables, lo viejo lo sigue mostrando).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from catalogo.models import CategoriaProducto, CategoriaReparacion, Marca, MetodoPago, ModeloEquipo, Reparacion

from .forms import (
    CategoriaProductoForm, CategoriaReparacionForm, MarcaForm, MetodoPagoForm, ModeloEquipoForm, ReparacionForm,
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
    return [(obj, [mostrar(obj) for _, mostrar in sec["columnas"]], getattr(obj, sec["activo"])) for obj in consulta]


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
