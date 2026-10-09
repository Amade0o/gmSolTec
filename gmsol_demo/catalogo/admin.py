"""Configuración del panel administrativo del catálogo."""

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from .models import CategoriaProducto, Marca, Producto, Cliente, Telefono, ModeloEquipo, CategoriaReparacion, Reparacion, OrdenTrabajo, EquipoRecibido, LineaReparacion #Estos son los modelos que se van a registrar en el panel de administracion, creados por mi

#Nota: Un modelo es una clase de django que tambien se va a la base de datos automaticamente
#Estas clases indican cómo se muestran y administran esos modelos.

@admin.register(CategoriaProducto)
class CategoriaProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa")


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    #Define que columnas se muestran en el listado de objetos
    list_display = ("nombre", "categoria", "marca", "precio_compra", "precio_venta", "margen", "activo")
    #Define que campos se pueden buscar usando el cuadro de busqueda
    list_filter = ("categoria", "activo")
    search_fields = ("nombre",)
    actions = None  # Deshabilita la acción de borrado masivo


#Regla personalizada
class TelefonoFormSet(BaseInlineFormSet):
    def clean(self):
        """Valida que cada cliente tenga al menos un teléfono cargado."""
        super().clean()
        cargados = [
            f for f in self.forms
            if getattr(f, "cleaned_data", None) and not f.cleaned_data.get("DELETE")
        ]
        if not cargados:
            raise ValidationError("El cliente debe tener al menos un teléfono.")


class TelefonoInline(admin.TabularInline):
    model = Telefono
    formset = TelefonoFormSet
    extra = 1


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre", "telefonos__numero")
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
    search_fields = ("nombre", "categoria")

@admin.register(LineaReparacion)
class LineaReparacionAdmin(admin.ModelAdmin):
    #Define que columnas se muestran en el listado de objetos
    list_display = ("reparacion", "equipo", "nota", "precio_orden")
    #Define que campos se pueden buscar usando el cuadro de busqueda
    list_filter = ("equipo", "reparacion")