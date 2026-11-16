"""Formularios de las pantallas propias.

Solo validan lo que es de la pantalla (formatos, campos obligatorios).
Las reglas del negocio las validan los modelos y catalogo/servicios.py.
"""
import re
from decimal import Decimal

from django import forms

from catalogo.models import (
    CategoriaProducto, Cliente, EquipoRecibido, Marca, LineaProductoOrden, LineaProductoVenta, LineaReparacion, MetodoPago,
    ModeloEquipo, Pago, Producto, Reparacion,
)


# ---------- Desplegables: solo lo activo, con textos claros ----------

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


class ElegirMetodo(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return texto_metodo(obj)


def metodos_activos():
    return MetodoPago.objects.filter(activo=True).order_by("nombre")


# ---------- Cliente de la orden: uno existente o uno nuevo ----------

class ClienteOrdenForm(forms.Form):
    cliente = ElegirCliente(queryset=clientes(), required=False, empty_label="Elegí un cliente…")
    nuevo_nombre = forms.CharField(max_length=120, required=False, label="Nombre")
    nuevo_telefono = forms.CharField(max_length=30, required=False, label="Teléfono")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].queryset = clientes()      # se vuelve a leer en cada pantalla

    def clean(self):
        datos = super().clean()
        if datos.get("cliente") and datos.get("nuevo_nombre"):
            raise forms.ValidationError("Elegí un cliente existente o cargá uno nuevo, no los dos.")
        if not datos.get("cliente") and not datos.get("nuevo_nombre"):
            raise forms.ValidationError("Falta el cliente: elegí uno o cargá su nombre.")
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
        self.fields["tipo"].choices = [("", "Elegí el tipo…")] + [c for c in self.fields["tipo"].choices if c[0]]
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
    class Meta:
        model = LineaReparacion
        fields = ["reparacion", "precio_vendido"]
        labels = {"reparacion": "Reparación", "precio_vendido": "Precio"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reparacion"].queryset = Reparacion.objects.filter(activo=True).order_by("categoria__nombre", "nombre")
        self.fields["reparacion"].empty_label = "Elegí la reparación…"


class LineaProductoForm(forms.ModelForm):
    class Meta:
        model = LineaProductoOrden
        fields = ["producto", "cantidad_adquirida", "precio_vendido"]
        labels = {"cantidad_adquirida": "Cantidad", "precio_vendido": "Precio c/u"}
        widgets = {"precio_vendido": forms.NumberInput(attrs={"placeholder": "De lista"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto"].queryset = Producto.objects.filter(activo=True).order_by("nombre")
        self.fields["producto"].label_from_instance = lambda p: f"{p.nombre} · ${p.precio_venta:,.0f}".replace(",", ".")
        self.fields["producto"].empty_label = "Elegí el producto…"
        self.fields["cantidad_adquirida"].initial = 1


class LineaProductoVentaForm(LineaProductoForm):
    class Meta(LineaProductoForm.Meta):
        model = LineaProductoVenta


class PagoForm(forms.ModelForm):
    metodo_pago = ElegirMetodo(queryset=metodos_activos(), label="Método", empty_label="Elegí el método…")

    class Meta:
        model = Pago
        fields = ["metodo_pago", "monto", "recargo_porcentaje"]
        labels = {"monto": "Monto", "recargo_porcentaje": "Recargo %"}
        widgets = {"recargo_porcentaje": forms.NumberInput(attrs={"placeholder": "El del método"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["metodo_pago"].queryset = metodos_activos()


# Formsets: varias filas del mismo formulario. Las filas vacías se ignoran.
# La primera reparación es obligatoria (min_num=1): viene cargada con "Revisión / diagnóstico".
ReparacionesFormSet = forms.formset_factory(LineaReparacionForm, extra=2, min_num=1, validate_min=True)
ProductosFormSet = forms.formset_factory(LineaProductoForm, extra=2)
ProductosVentaFormSet = forms.formset_factory(LineaProductoVentaForm, extra=2, min_num=1, validate_min=True)


# ---------- Formularios chicos del detalle de la orden ----------

class DevolucionForm(forms.Form):
    linea_reparacion = forms.ModelChoiceField(
        queryset=LineaReparacion.objects.none(), required=False, label="Devolver una reparación completa",
        empty_label="No, un monto")
    monto = forms.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=Decimal("0.01"),
                               label="Monto", widget=forms.NumberInput(attrs={"placeholder": "Vacío: el de la reparación"}))
    nota = forms.CharField(max_length=300, required=False, label="Nota")

    def __init__(self, *args, orden=None, **kwargs):
        super().__init__(*args, **kwargs)
        if orden is not None:
            # Solo reparaciones de equipos no arreglables de esta orden
            self.fields["linea_reparacion"].queryset = LineaReparacion.objects.filter(
                equipo__orden_trabajo=orden, equipo__estado="no_arreglable").select_related("reparacion")
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
    monto = forms.DecimalField(max_digits=10, decimal_places=2, required=False, label="Monto",
                               widget=forms.NumberInput(attrs={"placeholder": "Lo que falta"}))
    recargo_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, required=False, min_value=0,
                                            label="Recargo %", widget=forms.NumberInput(attrs={"placeholder": "El del método"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["metodo_pago"].queryset = metodos_activos()
        self.fields["metodo_pago"].empty_label = "Elegí el método…"


PagosVentaFormSet = forms.formset_factory(PagoVentaForm, extra=1, min_num=1, validate_min=True)


class EntregaForm(forms.Form):
    """Cobro del saldo al entregar el equipo."""
    metodo_pago = ElegirMetodo(queryset=metodos_activos(), required=False, label="Método",
                               empty_label="Elegí con qué paga…")
    recargo_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, required=False, min_value=0,
                                            label="Recargo %", widget=forms.NumberInput(attrs={"placeholder": "El del método"}))

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
    telefono = forms.CharField(max_length=30, required=False, label="Teléfono")

    class Meta(ClienteForm.Meta):
        fields = ["nombre", "telefono", "email", "direccion", "notas"]


class TelefonoForm(forms.Form):
    numero = forms.CharField(max_length=30, label="Teléfono")
    principal = forms.BooleanField(required=False, label="Principal")



# ---------- Productos ----------

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ["nombre", "categoria", "marca", "precio_compra", "precio_venta"]
        labels = {"categoria": "Categoría", "precio_compra": "Precio de compra", "precio_venta": "Precio de venta"}
        help_texts = {"precio_venta": "Cambiarlo no toca las ventas ya hechas: cada venta guarda su precio."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo las activas, pero si el producto ya tiene una desactivada, se sigue mostrando
        actual = self.instance
        categorias = CategoriaProducto.objects.filter(activa=True)
        marcas = Marca.objects.filter(activa=True)
        if actual.pk:
            categorias = categorias | CategoriaProducto.objects.filter(pk=actual.categoria_id)
            marcas = marcas | Marca.objects.filter(pk=actual.marca_id)
        self.fields["categoria"].queryset = categorias.order_by("nombre")
        self.fields["categoria"].empty_label = "Elegí la categoría…"
        self.fields["categoria"].limit_choices_to = None
        self.fields["marca"].queryset = marcas.order_by("nombre")
        self.fields["marca"].empty_label = "Sin marca"
        self.fields["marca"].limit_choices_to = None

    def _get_validation_exclusions(self):
        # El modelo solo acepta categorías y marcas activas. Si no se cambiaron, no se vuelven
        # a controlar: así se puede editar el precio de un producto cuya categoría se desactivó.
        excluir = super()._get_validation_exclusions()
        for campo in ("categoria", "marca"):
            if campo not in self.changed_data:
                excluir.add(campo)
        return excluir
