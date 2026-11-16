from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from catalogo.models import Devolucion, OrdenTrabajo


@login_required
def inicio(request):
    ordenes = (
        OrdenTrabajo.objects.filter(venta__isnull=True)      # las cerradas con venta ya no están en curso
        .select_related("cliente", "venta")
        .prefetch_related("equipos__modelo", "equipos__lineas_reparacion", "lineas_producto", "pagos", "devoluciones")
        .order_by("-id")
    )
    en_curso = [o for o in ordenes if o.estado in ("pendiente", "lista", "no_arreglable")]
    contexto = {
        "ordenes": en_curso,
        "en_revision": sum(1 for o in en_curso if o.estado == "pendiente"),
        "listas": sum(1 for o in en_curso if o.estado == "lista"),
        "devoluciones": Devolucion.objects.filter(fecha_devolucion__isnull=True).count(),
    }
    return render(request, "web/inicio.html", contexto)