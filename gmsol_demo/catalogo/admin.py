"""Configuración del panel administrativo del catálogo."""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from .models import CategoriaProducto, LineaProductoOrden, LineaProductoVenta, Marca, MetodoPago, Pago, Producto, Cliente, Telefono, ModeloEquipo, CategoriaReparacion, Reparacion, OrdenTrabajo, EquipoRecibido, LineaReparacion, Venta
from .servicios import cerrar_orden, ReglaDeNegocioError

#Nota: Un modelo es una clase de django que tambien se va a la base de datos automaticamente
#Estas clases indican cómo se muestran y administran esos modelos.

@admin.register(CategoriaProducto)
class CategoriaProductoAdmin(admin.ModelAdmin):
    # Define las columnas que se muestran en el listado del modelo.
    list_display = ("nombre", "activa")


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "marca", "precio_compra", "precio_venta", "margen", "activo")
    # Permite filtrar el listado mediante opciones en el panel lateral.
    list_filter = ("categoria", "activo")
    # Define los campos que se pueden buscar desde el cuadro de búsqueda.
    search_fields = ("nombre",)
    # Define las acciones disponibles para los objetos seleccionados.
    actions = None  # Deshabilita la acción de borrado masivo

class TelefonoInline(admin.TabularInline):
    model = Telefono
    extra = 1


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre", "telefonos__numero")
    # Define los inlines que se administran dentro de este modelo.
    inlines = [TelefonoInline]

@admin.register(ModeloEquipo)
class ModeloEquipoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "marca", "tipo", "activo")
    search_fields = ("nombre", "marca__nombre", "tipo")

@admin.register(CategoriaReparacion)
class CategoriaReparacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    search_fields = ("nombre",)

@admin.register(Reparacion)
class ReparacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "activo")
    search_fields = ("nombre", "categoria__nombre")

@admin.register(LineaReparacion)
class LineaReparacionAdmin(admin.ModelAdmin):
    list_display = ("reparacion", "nota", "precio_vendido", "equipo", "subtotal")
    list_filter = ("equipo", "reparacion")

#ES OBLIGATORIO DESDE EL LADO DERECHO DE LA RELACION, es solo para verificar que haya un elemento
class EquipoRecibidoFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        equipos = [
            f for f in self.forms
            if getattr(f, "cleaned_data", None) and not f.cleaned_data.get("DELETE")
        ]
        if not equipos:
            raise ValidationError("La orden debe tener al menos un equipo.")

class EquipoRecibidoInline(admin.TabularInline):
    model = EquipoRecibido
    formset = EquipoRecibidoFormSet
    extra = 1


@admin.register(LineaProductoOrden)
class LineaProductoOrdenAdmin(admin.ModelAdmin):
    list_display = ("cantidad_adquirida", "precio_vendido", "orden_trabajo", "subtotal")
    list_filter = ("producto",)
    search_fields = ("producto__nombre",)

@admin.register(LineaProductoVenta)
class LineaProductoVentaAdmin(admin.ModelAdmin):
    list_display = ("cantidad_adquirida", "precio_vendido", "venta", "subtotal")
    list_filter = ("producto",)
    search_fields = ("producto__nombre",)

class LineaProductoOrdenInline(admin.TabularInline):
    model = LineaProductoOrden
    extra = 1        
    autocomplete_fields = ("producto",)
    readonly_fields = ("subtotal",)

class LineaProductoVentaInline(admin.TabularInline):
    model = LineaProductoVenta
    extra = 1        
    autocomplete_fields = ("producto",)
    readonly_fields = ("subtotal",)

class PagoInline(admin.TabularInline):
    model = Pago
    extra = 1
    readonly_fields = ("recargo_monto", "total_cobrado", "retenido")

    def get_exclude(self, request, obj=None):
        exclude = list(super().get_exclude(request, obj) or [])
        # El FK del padre ya lo oculta el admin solo; ocultamos el otro due�o.
        if self.parent_model is OrdenTrabajo:
            exclude.append("venta")
        elif self.parent_model is Venta:
            exclude.append("orden_trabajo")
        return exclude

@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "fecha_recepcion", "estado", "total", "monto_adeudado", "adeuda")
    readonly_fields = ("estado", "total", "monto_pagado", "monto_adeudado", "monto_retenido")
    search_fields = ("=id", "cliente__nombre",)
    list_filter = ("fecha_recepcion",)
    inlines = [EquipoRecibidoInline, LineaProductoOrdenInline, PagoInline]
    actions = ["cerrar_ordenes"]

    @admin.action(description="Cerrar orden (crear venta)")
    def cerrar_ordenes(self, request, queryset):
        for orden in queryset:
            try:
                cerrar_orden(orden)
                self.message_user(request, f"Orden #{orden.id} cerrada.", level=messages.SUCCESS)
            except ReglaDeNegocioError as e:
                self.message_user(request, f"Orden #{orden.id}: {e}", level=messages.ERROR)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.cerrada:
            return False        # orden cerrada: solo lectura
        return super().has_change_permission(request, obj)

@admin.register(MetodoPago)
class MetodoPagoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cuenta", "recargo_porcentaje", "activo")
    list_filter = ("cuenta", "activo")
    search_fields = ("nombre", "cuenta")

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = (
        "id", "orden_trabajo", "venta", "metodo_pago", "monto",
        "recargo_porcentaje", "total_cobrado", "fecha",
    )
    list_filter = ("metodo_pago", "fecha")
    search_fields = ("=id",)

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "total")
    list_filter = ("fecha",)
    inlines = [LineaProductoVentaInline, PagoInline]

