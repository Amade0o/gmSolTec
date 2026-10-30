"""Configuración del panel administrativo del catálogo."""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from .models import CategoriaProducto, LineaProductoOrden, LineaProductoVenta, Marca, MetodoPago, Pago, Producto, Cliente, Telefono, ModeloEquipo, CategoriaReparacion, Reparacion, OrdenTrabajo, EquipoRecibido, LineaReparacion, Venta
from .servicios import cerrar_orden, ReglaDeNegocioError

#Nota: Un modelo es una clase de django que tambien se va a la base de datos automaticamente
#Estas clases indican cómo se muestran y administran esos modelos.


# ---------- Reglas de formulario (validan lo que se carga en las tablas "inline") ----------

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

class TelefonoFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        principales = [
            f for f in self.forms
            if getattr(f, "cleaned_data", None)
            and not f.cleaned_data.get("DELETE")
            and f.cleaned_data.get("principal")
        ]
        if len(principales) > 1:
            raise ValidationError("Solo un teléfono puede ser principal.")

class SinProductoRepetidoFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        productos = [
            f.cleaned_data["producto"] for f in self.forms
            if getattr(f, "cleaned_data", None)
            and not f.cleaned_data.get("DELETE")
            and f.cleaned_data.get("producto")
        ]
        if len(productos) != len(set(productos)):
            raise ValidationError("No repitas el mismo producto: sumá la cantidad en una sola fila.")


# ---------- Tablas inline (se cargan dentro de otra pantalla) ----------

class TelefonoInline(admin.TabularInline):
    model = Telefono
    formset = TelefonoFormSet
    extra = 1

class ModeloEquipoInline(admin.TabularInline):
    model = ModeloEquipo
    extra = 1

class ReparacionInline(admin.TabularInline):
    model = Reparacion
    extra = 1

class EquipoRecibidoInline(admin.TabularInline):
    model = EquipoRecibido
    formset = EquipoRecibidoFormSet
    extra = 1
    show_change_link = True     # enlace para abrir el equipo y cargarle sus reparaciones

class LineaReparacionInline(admin.TabularInline):
    model = LineaReparacion
    extra = 1

class LineaProductoOrdenInline(admin.TabularInline):
    model = LineaProductoOrden
    formset = SinProductoRepetidoFormSet
    extra = 1
    autocomplete_fields = ("producto",)
    readonly_fields = ("subtotal",)

class LineaProductoVentaInline(admin.TabularInline):
    model = LineaProductoVenta
    formset = SinProductoRepetidoFormSet
    extra = 1
    autocomplete_fields = ("producto",)
    readonly_fields = ("subtotal",)

class PagoInline(admin.TabularInline):
    model = Pago
    extra = 1
    readonly_fields = ("recargo_monto", "total_cobrado", "retenido")

    def get_exclude(self, request, obj=None):
        exclude = list(super().get_exclude(request, obj) or [])
        # El admin ya oculta solo la relacion con el padre; ocultamos la otra.
        if self.parent_model is OrdenTrabajo:
            exclude.append("venta")
        elif self.parent_model is Venta:
            exclude.append("orden_trabajo")
        return exclude


# ---------- Pantallas del catálogo ----------

@admin.register(CategoriaProducto)
class CategoriaProductoAdmin(admin.ModelAdmin):
    # Define las columnas que se muestran en el listado del modelo.
    list_display = ("nombre", "activa")


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa")
    inlines = [ModeloEquipoInline]


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "marca", "precio_compra", "precio_venta", "margen", "activo")
    # Permite filtrar el listado mediante opciones en el panel lateral.
    list_filter = ("categoria", "activo")
    # Define los campos que se pueden buscar desde el cuadro de búsqueda.
    search_fields = ("nombre",)
    # Define las acciones disponibles para los objetos seleccionados.
    actions = None  # Deshabilita la acción de borrado masivo


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
    inlines = [ReparacionInline]

@admin.register(Reparacion)
class ReparacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "activo")
    search_fields = ("nombre", "categoria__nombre")

@admin.register(MetodoPago)
class MetodoPagoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cuenta", "recargo_porcentaje", "activo")
    list_filter = ("cuenta", "activo")
    search_fields = ("nombre", "cuenta")


# ---------- Pantallas de orden, equipo, pago y venta ----------

@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "fecha_recepcion", "estado", "total", "monto_adeudado", "adeuda")
    search_fields = ("=id", "cliente__nombre",)
    list_filter = ("fecha_recepcion",)
    inlines = [EquipoRecibidoInline, LineaProductoOrdenInline, PagoInline]
    actions = ["cerrar_ordenes"]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:     # al crear una orden todavía no hay números que mostrar
            return ()
        return ("estado", "total", "monto_pagado", "monto_adeudado", "monto_retenido")

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

@admin.register(EquipoRecibido)
class EquipoRecibidoAdmin(admin.ModelAdmin):
    list_display = ("id", "orden_trabajo", "tipo", "modelo", "estado")
    list_filter = ("estado",)
    inlines = [LineaReparacionInline]

    def has_add_permission(self, request):
        return False            # los equipos se agregan desde la orden

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.orden_trabajo.cerrada:
            return False        # equipo de una orden cerrada: solo lectura
        return super().has_change_permission(request, obj)

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = (
        "id", "orden_trabajo", "venta", "metodo_pago", "monto",
        "recargo_porcentaje", "recargo_monto", "total_cobrado", "fecha",
    )
    list_filter = ("metodo_pago", "fecha")
    search_fields = ("=id",)

    # Solo para mirar: los pagos se cargan desde la orden o desde la venta
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "total", "cliente", "orden_trabajo")
    list_filter = ("fecha",)
    readonly_fields = ("orden_trabajo",)    # las ventas de una orden se crean con "Cerrar orden"
    inlines = [LineaProductoVentaInline, PagoInline]
    actions = None                          # sin borrado masivo

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.orden_trabajo_id:
            return False        # la venta de una orden no se borra
        return super().has_delete_permission(request, obj)
