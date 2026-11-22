"""Formularios de las pantallas propias.

Solo validan lo que es de la pantalla (formatos, campos obligatorios).
Las reglas del negocio las validan los modelos y negocio/servicios/.
"""
import re
from decimal import Decimal

from django import forms
from django.urls import reverse

from negocio.models import (
    CategoriaProducto, CategoriaReparacion, Cliente, EquipoRecibido, Marca, LineaProductoOrden, LineaProductoVenta, LineaReparacion, MetodoPago,
    ModeloEquipo, Pago, Producto, Reparacion, TipoEquipo,
)


# ---------- Desplegables: solo lo activo, con textos claros ----------

def con_alta_rapida(campo, seccion):
    """Marca un desplegable del catálogo: la pantalla le pone un botón "+ Nuevo" que lo carga
    sin salir de la pantalla (ver views_catalogo.alta_rapida)."""
    campo.widget.attrs["data-catalogo"] = seccion


class SelectConPrecio(forms.Select):
    """Desplegable de productos: cada opción lleva su precio de lista (data-precio), para
    mostrarlo en la fila y poder cambiarlo con el lápiz."""
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcion = super().create_option(name, value, label, selected, index, subindex, attrs)
        producto = getattr(value, "instance", None)
        if producto is not None:
            opcion["attrs"]["data-precio"] = f"{producto.precio_venta}"
        return opcion


def clientes():
    return Cliente.objects.prefetch_related("telefonos").order_by("nombre")


def texto_cliente(cliente):
    telefonos = [t.numero for t in cliente.telefonos.all()]
    return f"{cliente.nombre} · {telefonos[0]}" if telefonos else cliente.nombre


def texto_metodo(metodo):
    if metodo.recargo_porcentaje:
        return f"{metodo.nombre} (+{metodo.recargo_porcentaje:g}%)"
    return metodo.nombre


class ElegirCliente(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return texto_cliente(obj)


class SelectConRecargo(forms.Select):
    """Desplegable de métodos de pago: cada opción lleva su recargo (data-recargo), para mostrarlo
    en el campo "Recargo %" con un lápiz para cambiarlo."""
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcion = super().create_option(name, value, label, selected, index, subindex, attrs)
        metodo = getattr(value, "instance", None)
        if metodo is not None:
            opcion["attrs"]["data-recargo"] = f"{metodo.recargo_porcentaje}"
        return opcion


class ElegirMetodo(forms.ModelChoiceField):
    widget = SelectConRecargo(attrs={"data-con-recargo": ""})

    def label_from_instance(self, obj):
        return texto_metodo(obj)


def metodos_activos():
    return MetodoPago.objects.filter(activo=True).order_by("nombre")


# Teléfono: type="tel" abre el teclado numérico en el celular.
# Sin autocomplete="tel": son datos del cliente, no de quien atiende el mostrador.
def campo_telefono(**kwargs):
    return forms.CharField(max_length=30, widget=forms.TextInput(attrs={"type": "tel", "spellcheck": "false"}), **kwargs)


# ---------- Cliente de la orden: uno existente o uno nuevo ----------

class ClienteOrdenForm(forms.Form):
    """El cliente de la orden: uno de la lista O uno nuevo. Lo decide "modo"; lo del otro modo se ignora
    (así no se puede elegir uno de la lista y cargar uno nuevo a la vez)."""
    modo = forms.ChoiceField(choices=[("existente", "De la lista"), ("nuevo", "Cliente nuevo")],
                             widget=forms.RadioSelect, initial="existente", required=False, label="Cliente")
    cliente = ElegirCliente(queryset=clientes(), required=False, empty_label="Elegí un cliente…")
    nuevo_nombre = forms.CharField(max_length=120, required=False, label="Nombre")
    nuevo_telefono = campo_telefono(required=False, label="Teléfono")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].queryset = clientes()      # se vuelve a leer en cada pantalla
        # Al escribir el nombre o el teléfono del cliente nuevo, avisa si ya existe uno parecido
        for campo in ("nuevo_nombre", "nuevo_telefono"):
            self.fields[campo].widget.attrs.update({
                "hx-get": reverse("web:clientes_parecidos"), "hx-trigger": "input changed delay:400ms",
                "hx-target": "#clientes-parecidos", "hx-sync": "this:replace", "data-no-resumen": "",
                "hx-include": f"[name='{self.add_prefix('nuevo_nombre')}'],[name='{self.add_prefix('nuevo_telefono')}']",
            })

    def clean(self):
        datos = super().clean()
        if datos.get("modo") == "nuevo":
            datos["cliente"] = None
            if not datos.get("nuevo_nombre"):
                self.add_error("nuevo_nombre", "Escribí el nombre del cliente nuevo.")
        else:
            datos["modo"] = "existente"
            datos["nuevo_nombre"], datos["nuevo_telefono"] = "", ""
            if not datos.get("cliente"):
                raise forms.ValidationError("Falta el cliente: elegilo de la lista o tocá «Cliente nuevo».")
        return datos


# ---------- Equipo ----------

class EquipoForm(forms.ModelForm):
    class Meta:
        model = EquipoRecibido
        fields = ["tipo", "modelo", "problema", "tipo_bloqueo", "clave_bloqueo", "accesorios_dejados"]
        widgets = {
            "tipo_bloqueo": forms.RadioSelect,
            "problema": forms.Textarea(attrs={"rows": 2}),
            "accesorios_dejados": forms.Textarea(attrs={"rows": 2, "placeholder": "Funda, chip, cargador…"}),
        }
        labels = {
            "problema": "Problema / qué hay que hacer",
            "tipo_bloqueo": "Bloqueo",
            "clave_bloqueo": "Clave",
            "accesorios_dejados": "Accesorios que deja",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["modelo"].queryset = ModeloEquipo.objects.filter(activo=True).select_related("marca").order_by("marca__nombre", "nombre")
        self.fields["modelo"].label_from_instance = lambda m: f"{m.marca} {m.nombre}"
        self.fields["modelo"].empty_label = "Sin modelo (PC u otro)"
        con_alta_rapida(self.fields["modelo"], "modelos")
        self.fields["tipo"].queryset = TipoEquipo.objects.filter(activo=True)
        self.fields["tipo"].empty_label = "Elegí el tipo…"
        con_alta_rapida(self.fields["tipo"], "tipos-equipo")
        # "Ninguno" primero: es el valor por defecto
        self.fields["tipo_bloqueo"].choices = [("ninguno", "Ninguno"), ("pin", "PIN"), ("patron", "Patrón"), ("contrasena", "Contraseña")]

    def clean(self):
        datos = super().clean()
        tipo, clave = datos.get("tipo_bloqueo"), datos.get("clave_bloqueo", "")
        if tipo in ("pin", "patron", "contrasena") and not clave:
            self.add_error("clave_bloqueo", "Cargá la clave del bloqueo.")
        if tipo == "pin" and clave and not clave.isdigit():
            self.add_error("clave_bloqueo", "El PIN tiene que ser solo números.")
        if tipo == "patron" and clave and not re.fullmatch(r"[1-9](-[1-9])+", clave):
            self.add_error("clave_bloqueo", "El patrón se guarda como puntos separados por guiones, por ejemplo 1-5-9-6.")
        if tipo == "patron" and clave and len(set(clave.split("-"))) != len(clave.split("-")):
            self.add_error("clave_bloqueo", "Un patrón no repite puntos.")
        return datos


# ---------- Líneas: primero qué se hace o se vende, después el precio ----------

class LineaReparacionForm(forms.ModelForm):
    """Una reparación. «Revisión / diagnóstico» va una sola vez por equipo: solo en la primera fila
    (las filas 2, 3… y la fila vacía que se copia no la ofrecen) o si el equipo todavía no la tiene."""
    class Meta:
        model = LineaReparacion
        fields = ["reparacion", "precio_vendido"]
        labels = {"reparacion": "Reparación", "precio_vendido": "Precio"}

    def __init__(self, *args, sin_revision=None, **kwargs):
        super().__init__(*args, **kwargs)
        reparaciones = Reparacion.objects.filter(activo=True).order_by("categoria__nombre", "nombre")
        if sin_revision is None:        # en una lista de filas: solo la primera la ofrece
            sin_revision = bool(re.search(r"-(\d+|__prefix__)$", self.prefix or "")) and not self.prefix.endswith("-0")
        if sin_revision:
            reparaciones = reparaciones.exclude(nombre__iexact=Reparacion.NOMBRE_REVISION)
        self.fields["reparacion"].queryset = reparaciones
        self.fields["reparacion"].empty_label = "Elegí la reparación…"
        con_alta_rapida(self.fields["reparacion"], "reparaciones")


class LineaProductoForm(forms.ModelForm):
    """Una fila de producto. La cantidad vacía es 1 y el precio vacío es el de lista
    (la pantalla lo muestra con un lápiz para cambiarlo). Una fila sin producto se ignora."""
    class Meta:
        model = LineaProductoOrden
        fields = ["producto", "cantidad_adquirida", "precio_vendido"]
        labels = {"cantidad_adquirida": "Cantidad", "precio_vendido": "Precio c/u"}
        widgets = {
            "producto": SelectConPrecio(attrs={"data-con-precio": ""}),
            "cantidad_adquirida": forms.NumberInput(attrs={"min": "1"}),     # vacía = 1
            "precio_vendido": forms.NumberInput(attrs={"placeholder": "Precio de lista", "data-por-defecto": "precio"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto"].queryset = Producto.objects.filter(activo=True).order_by("nombre")
        self.fields["producto"].label_from_instance = lambda p: p.nombre
        self.fields["producto"].empty_label = "Elegí el producto…"
        self.fields["cantidad_adquirida"].required = False

    def has_changed(self):
        # Sin producto la fila está vacía, aunque tenga una cantidad escrita
        return bool(self.data.get(self.add_prefix("producto"))) if self.is_bound else super().has_changed()

    def clean_cantidad_adquirida(self):
        return self.cleaned_data.get("cantidad_adquirida") or 1


class LineaProductoVentaForm(LineaProductoForm):
    class Meta(LineaProductoForm.Meta):
        model = LineaProductoVenta


class PagoForm(forms.ModelForm):
    metodo_pago = ElegirMetodo(queryset=metodos_activos(), label="Método", empty_label="Elegí el método…")

    class Meta:
        model = Pago
        fields = ["metodo_pago", "monto", "recargo_porcentaje"]
        labels = {"monto": "Monto", "recargo_porcentaje": "Recargo %"}
        widgets = {"recargo_porcentaje": forms.NumberInput(attrs={"placeholder": "El del método", "data-por-defecto": "recargo"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["metodo_pago"].queryset = metodos_activos()


# Formsets: varias filas del mismo formulario. Se muestra UNA fila; "+ Agregar otra" suma filas
# (app.js copia la fila vacía). Las filas vacías se ignoran.
# La primera reparación es obligatoria (min_num=1): viene cargada con "Revisión / diagnóstico".
class _ReparacionesBase(forms.BaseFormSet):
    def clean(self):
        super().clean()
        revisiones = [f for f in self.forms if f.cleaned_data.get("reparacion") and f.cleaned_data["reparacion"].es_revision]
        if len(revisiones) > 1:
            raise forms.ValidationError("«Revisión / diagnóstico» va una sola vez.")


ReparacionesFormSet = forms.formset_factory(LineaReparacionForm, formset=_ReparacionesBase, extra=0, min_num=1, validate_min=True)
ProductosFormSet = forms.formset_factory(LineaProductoForm, extra=1)
ProductosVentaFormSet = forms.formset_factory(LineaProductoVentaForm, extra=0, min_num=1, validate_min=True)


# ---------- Formularios chicos del detalle de la orden ----------

class DevolucionForm(forms.Form):
    linea_reparacion = forms.ModelChoiceField(
        queryset=LineaReparacion.objects.none(), required=False, label="Devolver una reparación completa",
        empty_label="No, un monto")
    monto = forms.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=Decimal("0.01"),
                               label="Monto", widget=forms.NumberInput(attrs={"placeholder": "Vacío: se calcula solo"}))
    nota = forms.CharField(max_length=300, required=False, label="Nota")

    def __init__(self, *args, orden=None, **kwargs):
        super().__init__(*args, **kwargs)
        if orden is not None:
            # Cualquier reparación de esta orden que todavía no se devolvió
            self.fields["linea_reparacion"].queryset = LineaReparacion.objects.filter(
                equipo__orden_trabajo=orden, devoluciones__isnull=True).select_related("reparacion")
            self.fields["linea_reparacion"].label_from_instance = (
                lambda l: f"Equipo {l.equipo_id} · {l.reparacion} · ${l.precio_vendido:,.0f}".replace(",", "."))


class MetodoForm(forms.Form):
    metodo_pago = ElegirMetodo(queryset=metodos_activos(), label="Método", empty_label="Elegí el método…")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["metodo_pago"].queryset = metodos_activos()


# ---------- Pagos de la venta rápida y de la entrega ----------

class PagoVentaForm(forms.Form):
    """Como PagoForm, pero el monto puede quedar vacío: se completa con lo que falta."""
    metodo_pago = ElegirMetodo(queryset=metodos_activos(), label="Método")
    # Vacío = lo que falta; si se escribe, como en Pago.monto: al menos $ 0,01 (nunca negativo)
    monto = forms.DecimalField(max_digits=10, decimal_places=2, required=False, label="Monto", min_value=Decimal("0.01"),
                               widget=forms.NumberInput(attrs={"data-por-defecto": "resto"}))
    recargo_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, required=False, min_value=0,
                                            label="Recargo %", widget=forms.NumberInput(attrs={"placeholder": "El del método", "data-por-defecto": "recargo"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["metodo_pago"].queryset = metodos_activos()
        self.fields["metodo_pago"].empty_label = "Elegí el método…"


PagosVentaFormSet = forms.formset_factory(PagoVentaForm, extra=0, min_num=1, validate_min=True)


class EntregaForm(forms.Form):
    """Cobro del saldo al entregar el equipo."""
    metodo_pago = ElegirMetodo(queryset=metodos_activos(), required=False, label="Método",
                               empty_label="Elegí con qué paga…")
    recargo_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, required=False, min_value=0,
                                            label="Recargo %", widget=forms.NumberInput(attrs={"placeholder": "El del método", "data-por-defecto": "recargo"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["metodo_pago"].queryset = metodos_activos()


# ---------- Clientes ----------

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nombre", "email", "direccion", "notas"]
        labels = {"direccion": "Dirección", "notas": "Notas"}
        widgets = {"notas": forms.Textarea(attrs={"rows": 2, "placeholder": "Algo para recordar de este cliente"})}


class ClienteNuevoForm(ClienteForm):
    telefono = campo_telefono(required=False, label="Teléfono")

    class Meta(ClienteForm.Meta):
        fields = ["nombre", "telefono", "email", "direccion", "notas"]


class TelefonoForm(forms.Form):
    numero = campo_telefono(label="Teléfono")
    principal = forms.BooleanField(required=False, label="Principal")



# ---------- Formularios con desplegables de cosas que se pueden desactivar ----------

class ConDesactivablesForm(forms.ModelForm):
    """Base para Producto, Modelo y Reparación.

    En los desplegables (categoría, marca) solo aparecen los activos, pero si el registro ya
    tiene uno desactivado se sigue mostrando, y mientras no se cambie no se vuelve a controlar:
    así se puede editar un producto cuya categoría se desactivó.
    """
    campos_desactivables = {}       # campo -> (texto si está vacío, filtro de activos)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._excluir_sin_cambios = True
        for campo, (vacio, activos) in self.campos_desactivables.items():
            relacion = self._meta.model._meta.get_field(campo)
            modelo = relacion.related_model
            opciones = modelo.objects.filter(**activos)
            actual = getattr(self.instance, relacion.attname, None)
            if actual:     # el valor que ya tiene (por id, o por clave en los tipos de equipo)
                opciones = opciones | modelo.objects.filter(**{relacion.target_field.attname: actual})
            self.fields[campo].queryset = opciones.order_by("nombre")
            self.fields[campo].empty_label = vacio
            self.fields[campo].limit_choices_to = None

    def _get_validation_exclusions(self):
        excluir = super()._get_validation_exclusions()
        if self._excluir_sin_cambios:
            excluir |= {c for c in self.campos_desactivables if c not in self.changed_data}
        return excluir

    # Los nombres repetidos (ej.: mismo modelo en la misma marca) sí se controlan siempre
    def validate_unique(self):
        self._excluir_sin_cambios = False
        try:
            super().validate_unique()
        finally:
            self._excluir_sin_cambios = True

    def validate_constraints(self):
        self._excluir_sin_cambios = False
        try:
            super().validate_constraints()
        finally:
            self._excluir_sin_cambios = True


# ---------- Productos ----------

class ProductoForm(ConDesactivablesForm):
    campos_desactivables = {
        "categoria": ("Elegí la categoría…", {"activa": True}),
        "marca": ("Sin marca", {"activa": True}),
    }

    class Meta:
        model = Producto
        fields = ["nombre", "categoria", "marca", "precio_compra", "precio_venta"]
        labels = {"categoria": "Categoría", "precio_compra": "Precio de compra", "precio_venta": "Precio de venta"}
        help_texts = {"precio_venta": "Cambiarlo no toca las ventas ya hechas: cada venta guarda su precio."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        con_alta_rapida(self.fields["categoria"], "categorias-producto")
        con_alta_rapida(self.fields["marca"], "marcas")


# ---------- Catálogo (una pestaña por tabla) ----------

class CategoriaProductoForm(forms.ModelForm):
    class Meta:
        model = CategoriaProducto
        fields = ["nombre"]


class MarcaForm(forms.ModelForm):
    class Meta:
        model = Marca
        fields = ["nombre"]


class ModeloEquipoForm(ConDesactivablesForm):
    campos_desactivables = {"marca": ("Elegí la marca…", {"activa": True}), "tipo": ("Elegí el tipo…", {"activo": True})}

    class Meta:
        model = ModeloEquipo
        fields = ["marca", "nombre", "tipo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        con_alta_rapida(self.fields["marca"], "marcas")
        con_alta_rapida(self.fields["tipo"], "tipos-equipo")


class TipoEquipoForm(forms.ModelForm):
    class Meta:
        model = TipoEquipo
        fields = ["nombre"]
        help_texts = {"nombre": "Por ejemplo: Tablet, Consola, Smartwatch."}


class CategoriaReparacionForm(forms.ModelForm):
    class Meta:
        model = CategoriaReparacion
        fields = ["nombre"]


class ReparacionForm(ConDesactivablesForm):
    campos_desactivables = {"categoria": ("Elegí la categoría…", {"activo": True})}

    class Meta:
        model = Reparacion
        fields = ["categoria", "nombre"]
        labels = {"categoria": "Categoría"}
        help_texts = {"nombre": "El precio no va acá: se pone en cada orden."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        con_alta_rapida(self.fields["categoria"], "categorias-reparacion")


# ---------- Alta rápida desde otra pantalla (sin salir de la orden o del producto) ----------
# Modelo y reparación necesitan una marca o categoría: se elige de la lista o se escribe una nueva.

class _ConPadreNuevo:
    campo_padre = ""            # "marca" / "categoria"
    modelo_padre = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        padre = self.fields[self.campo_padre]
        padre.required = False
        padre.widget.attrs.pop("data-catalogo", None)       # sin un "+ Nuevo" adentro del "+ Nuevo"
        self.order_fields([self.campo_padre, "nuevo_padre"])

    def clean(self):
        datos = super().clean()
        nuevo = (datos.get("nuevo_padre") or "").strip()
        if nuevo:
            # Si ya existe con ese nombre se usa esa; si no, se crea (la vista deshace todo si el resto falla)
            padre = self.modelo_padre.objects.filter(nombre__iexact=nuevo).first()
            datos[self.campo_padre] = padre or self.modelo_padre.objects.create(nombre=nuevo)
        elif not datos.get(self.campo_padre):
            self.add_error(self.campo_padre, "Elegí una de la lista o escribí una nueva.")
        return datos


class ModeloRapidoForm(_ConPadreNuevo, ModeloEquipoForm):
    campo_padre, modelo_padre, texto_nuevo = "marca", Marca, "Escribir una marca nueva"
    nuevo_padre = forms.CharField(max_length=60, required=False, label="Marca nueva")


class ReparacionRapidaForm(_ConPadreNuevo, ReparacionForm):
    campo_padre, modelo_padre, texto_nuevo = "categoria", CategoriaReparacion, "Escribir una categoría nueva"
    nuevo_padre = forms.CharField(max_length=60, required=False, label="Categoría nueva")


class MetodoPagoForm(forms.ModelForm):
    class Meta:
        model = MetodoPago
        fields = ["nombre", "cuenta", "recargo_porcentaje"]
        labels = {"recargo_porcentaje": "Recargo %"}
        help_texts = {"recargo_porcentaje": "Cambiarlo no toca los pagos ya hechos: cada pago guarda su recargo."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cuenta"].choices = [("", "Elegí la cuenta…")] + [c for c in self.fields["cuenta"].choices if c[0]]
