"""Configuración del panel administrativo del catálogo."""

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from .models import CategoriaProducto, Marca, MetodoPago, Pago, Producto, Cliente, Telefono, ModeloEquipo, CategoriaReparacion, Reparacion, OrdenTrabajo, EquipoRecibido, LineaReparacion, LineaProducto #Estos son los modelos que se van a registrar en el panel de administracion, creados por mi

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
    list_display = ("reparacion", "nota", "precio_en_orden", "equipo", "subtotal")
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


@admin.register(LineaProducto)
class LineaProductoAdmin(admin.ModelAdmin):
    list_display = ("cantidad_adquirida", "precio_en_orden", "orden_trabajo", "subtotal")
    list_filter = ("producto",)
    search_fields = ("producto__nombre",)

class LineaProductoInline(admin.TabularInline):
    model = LineaProducto
    extra = 1        
    autocomplete_fields = ("producto",)
    readonly_fields = ("subtotal",)

class PagoInline(admin.TabularInline):
    model = Pago
    extra = 1
    readonly_fields = ("recargo_monto", "total_cobrado")

@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "fecha_recepcion", "estado", "adeuda")
    search_fields = ("=id", "cliente__nombre",)
    list_filter = ("fecha_recepcion",)
    inlines = [EquipoRecibidoInline, LineaProductoInline, PagoInline]

@admin.register(MetodoPago)
class MetodoPagoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cuenta", "recargo_porcentaje", "activo")
    list_filter = ("cuenta", "activo")
    search_fields = ("nombre", "cuenta")



