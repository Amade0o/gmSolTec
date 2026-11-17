"""Direcciones de la interfaz propia: cada pantalla y la vista que la atiende."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views, views_catalogo

app_name = "web"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("login/", auth_views.LoginView.as_view(template_name="web/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Órdenes de trabajo
    path("ordenes/", views.ordenes, name="ordenes"),
    path("ordenes/nueva/", views.orden_nueva, name="orden_nueva"),
    path("ordenes/nueva/resumen/", views.orden_nueva_resumen, name="orden_nueva_resumen"),
    path("ordenes/<int:numero>/", views.orden_detalle, name="orden_detalle"),
    path("ordenes/<int:numero>/entregar/", views.orden_entregar, name="orden_entregar"),

    # Acciones frecuentes de la franja superior
    path("entregar/", views.entregar, name="entregar"),
    path("ventas/rapida/", views.venta_rapida, name="venta_rapida"),
    path("ventas/rapida/resumen/", views.venta_rapida_resumen, name="venta_rapida_resumen"),

    # Ventas: las directas y las que cerraron una orden
    path("ventas/", views.ventas, name="ventas"),
    path("ventas/<int:numero>/", views.venta_detalle, name="venta_detalle"),

    # Devoluciones: acá se marca que el dinero ya se devolvió
    path("devoluciones/", views.devoluciones, name="devoluciones"),

    # Clientes
    path("clientes/", views.lista_clientes, name="clientes"),
    path("clientes/nuevo/", views.cliente_nuevo, name="cliente_nuevo"),
    path("clientes/buscar/", views.buscar_clientes, name="buscar_clientes"),
    path("clientes/<int:numero>/", views.cliente_detalle, name="cliente_detalle"),

    # Productos (el stock llega con la etapa 4)
    path("productos/", views.productos, name="productos"),
    path("productos/nuevo/", views.producto_nuevo, name="producto_nuevo"),
    path("productos/margen/", views.producto_margen, name="producto_margen"),
    path("productos/<int:numero>/", views.producto_detalle, name="producto_detalle"),

    # Catálogo: categorías, marcas, modelos, reparaciones y métodos de pago
    path("catalogo/", views_catalogo.catalogo, name="catalogo_inicio"),
    path("catalogo/<slug:seccion>/", views_catalogo.catalogo, name="catalogo"),
    path("catalogo/<slug:seccion>/<int:numero>/", views_catalogo.catalogo_editar, name="catalogo_editar"),
]
