"""Configuración del panel administrativo del catálogo."""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import Cambio, MovimientoCaja, Devolucion, CategoriaProducto, LineaProductoOrden, LineaProductoVenta, Marca, MetodoPago, Pago, Producto, Cliente, Telefono, ModeloEquipo, CategoriaReparacion, Reparacion, OrdenTrabajo, EquipoRecibido, LineaReparacion, Venta, TipoEquipo
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
    fields = ("reparacion", "precio_vendido", "nota")      # primero qué se hace, después el precio
    extra = 1

class LineaProductoOrdenInline(admin.TabularInline):
    model = LineaProductoOrden
    formset = SinProductoRepetidoFormSet
    fields = ("producto", "cantidad_adquirida", "precio_vendido", "subtotal")
    extra = 1
    autocomplete_fields = ("producto",)
    readonly_fields = ("subtotal",)

class LineaProductoVentaInline(admin.TabularInline):
    model = LineaProductoVenta
    formset = SinProductoRepetidoFormSet
    fields = ("producto", "cantidad_adquirida", "precio_vendido", "subtotal")
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

class DevolucionInline(admin.TabularInline):
    """Dentro de la orden solo se REGISTRA que hay que devolver dinero.
    Marcar que ya se devolvió se hace en el menú Devoluciones."""
    model = Devolucion
    fields = ("linea_reparacion", "monto", "nota", "estado")
    readonly_fields = ("estado",)
    extra = 0
    can_delete = False      # una devolución mal cargada se borra desde el menú Devoluciones

    @admin.display(description="Estado")
    def estado(self, obj):
        if obj is None or obj.pk is None:
            return "-"
        return "Ya devuelta" if obj.devuelta else "Falta devolver"

    def get_formset(self, request, obj=None, **kwargs):
        request._orden_actual = obj         # para mostrar solo las reparaciones de esta orden
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        campo = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "linea_reparacion":
            orden = getattr(request, "_orden_actual", None)
            campo.queryset = LineaReparacion.objects.filter(equipo__orden_trabajo=orden) if orden else LineaReparacion.objects.none()
            campo.label_from_instance = lambda l: f"Equipo #{l.equipo_id} · {l.reparacion} · ${l.precio_vendido}"
        return campo


# ---------- Pantallas del catálogo ----------

@admin.register(CategoriaProducto)
class CategoriaProductoAdmin(admin.ModelAdmin):
    # Define las columnas que se muestran en el listado del modelo.
    list_display = ("nombre", "activa")


@admin.register(TipoEquipo)
class TipoEquipoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "clave", "activo")
    list_filter = ("activo",)


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
    search_fields = ("nombre", "marca__nombre", "tipo__nombre")

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
    list_display = ("id", "cliente", "fecha_recepcion", "estado", "total", "saldo", "adeuda", "monto_a_devolver")
    search_fields = ("=id", "cliente__nombre",)
    list_filter = ("fecha_recepcion",)
    inlines = [EquipoRecibidoInline, LineaProductoOrdenInline, PagoInline, DevolucionInline]
    actions = ["cerrar_ordenes"]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:     # al crear una orden todavía no hay números que mostrar
            return ()
        return ("estado", "total", "monto_pagado", "saldo", "monto_retenido", "monto_devuelto", "monto_a_devolver")

    @admin.display(description="Saldo")
    def saldo(self, orden):
        pendiente = orden.monto_adeudado
        if pendiente > 0:
            return f"Debe ${pendiente}"
        if pendiente < 0:
            return f"A favor del cliente: ${-pendiente} (se debe devolver)"
        return "Saldado"

    def change_view(self, request, object_id, form_url="", extra_context=None):
        orden = self.get_object(request, object_id)
        extra_context = extra_context or {}
        if orden is not None:
            extra_context["title"] = f"Orden #{orden.id} · {orden.cliente} · {orden.estado}"
        return super().change_view(request, object_id, form_url, extra_context)

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

    def change_view(self, request, object_id, form_url="", extra_context=None):
        equipo = self.get_object(request, object_id)
        extra_context = extra_context or {}
        if equipo is not None:
            orden = equipo.orden_trabajo
            extra_context["title"] = f"Orden #{orden.id} · {orden.cliente} · Equipo #{equipo.id}"
        return super().change_view(request, object_id, form_url, extra_context)

    def response_change(self, request, obj):
        respuesta = super().response_change(request, obj)
        if "_save" in request.POST:     # "Guardar" vuelve al menú de órdenes
            return HttpResponseRedirect(reverse("admin:negocio_ordentrabajo_changelist"))
        return respuesta

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.orden_trabajo.cerrada:
            return False        # equipo de una orden cerrada: solo lectura
        return super().has_change_permission(request, obj)

class EstadoDevolucionFilter(admin.SimpleListFilter):
    title = "estado"
    parameter_name = "estado"

    def lookups(self, request, model_admin):
        return [("pendiente", "Falta devolver"), ("devuelta", "Ya devuelta")]

    def queryset(self, request, queryset):
        if self.value() == "pendiente":
            return queryset.filter(fecha_devolucion__isnull=True)
        if self.value() == "devuelta":
            return queryset.filter(fecha_devolucion__isnull=False)
        return queryset

@admin.register(Devolucion)
class DevolucionAdmin(admin.ModelAdmin):
    """Acá se marca que el dinero ya se devolvió: elegí el método y guardá."""
    list_display = ("id", "orden_trabajo", "monto", "estado", "metodo_pago", "fecha_devolucion")
    list_filter = (EstadoDevolucionFilter,)
    fields = ("orden_trabajo", "linea_reparacion", "monto", "nota", "metodo_pago", "fecha_devolucion")
    readonly_fields = ("orden_trabajo", "linea_reparacion", "monto", "fecha_devolucion")
    actions = None          # sin borrado masivo

    @admin.display(description="Estado")
    def estado(self, obj):
        return "Ya devuelta" if obj.devuelta else "Falta devolver"

    def has_add_permission(self, request):
        return False        # se registran desde la orden

    def has_delete_permission(self, request, obj=None):
        if obj is not None and (obj.devuelta or obj.orden_trabajo.cerrada):
            return False        # solo se borra una devolución pendiente (cargada por error)
        return super().has_delete_permission(request, obj)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        devolucion = self.get_object(request, object_id)
        extra_context = extra_context or {}
        if devolucion is not None:
            orden = devolucion.orden_trabajo
            extra_context["title"] = f"Devolución · Orden #{orden.id} · {orden.cliente} · ${devolucion.monto}"
        return super().change_view(request, object_id, form_url, extra_context)

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

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.orden_trabajo_id:
            return False        # la venta de una orden no se modifica: solo lectura
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.orden_trabajo_id:
            return False        # la venta de una orden no se borra
        return super().has_delete_permission(request, obj)


# ---------- Caja e historial (etapa 4): solo para mirar ----------
# Se cargan, corrigen y anulan desde la pantalla Caja, que pasa por los servicios y deja todo en el
# historial. Si el admin dejara editarlos, ese control se podría saltear.

class SoloLecturaAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(SoloLecturaAdmin):
    list_display = ("fecha", "caja", "tipo", "descripcion", "monto", "anulado")
    list_filter = ("caja", "tipo", "anulado")
    search_fields = ("descripcion", "nota")


@admin.register(Cambio)
class CambioAdmin(SoloLecturaAdmin):
    list_display = ("fecha", "area", "accion", "frase")
    list_filter = ("area", "accion")
    search_fields = ("frase",)
