"""Tests de la etapa 1: catálogo (módulo 1).

Correr solo este archivo:
    python manage.py test catalogo.tests.test_etapa1_catalogo
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from catalogo.models import (
    CategoriaProducto,
    CategoriaReparacion,
    Cliente,
    Marca,
    ModeloEquipo,
    Producto,
    Reparacion,
    Telefono,
)


def crear_producto(nombre="Cable USB-C", compra="1000.00", venta="1500.00", marca=None):
    categoria, _ = CategoriaProducto.objects.get_or_create(nombre="Cables")
    return Producto.objects.create(
        nombre=nombre,
        categoria=categoria,
        marca=marca,
        precio_compra=Decimal(compra),
        precio_venta=Decimal(venta),
    )


class ProductoTests(TestCase):
    def test_margen_se_calcula_con_los_dos_precios(self):
        producto = crear_producto(compra="1000.00", venta="1500.00")
        self.assertEqual(producto.margen, 50)

    def test_margen_es_none_si_el_precio_de_compra_es_cero(self):
        producto = crear_producto(compra="0.00", venta="1500.00")
        self.assertIsNone(producto.margen)

    def test_margen_no_se_guarda_como_campo(self):
        campos = [campo.name for campo in Producto._meta.get_fields()]
        self.assertNotIn("margen", campos)

    def test_la_marca_es_opcional(self):
        producto = crear_producto(marca=None)
        producto.full_clean()
        self.assertIsNone(producto.marca)

    def test_las_relaciones_se_pueden_recorrer_en_ambos_sentidos(self):
        marca = Marca.objects.create(nombre="Samsung")
        producto = crear_producto(marca=marca)
        self.assertEqual(producto.categoria.productos.count(), 1)
        self.assertEqual(marca.productos.count(), 1)

    def test_no_se_puede_borrar_una_categoria_con_productos(self):
        producto = crear_producto()
        with self.assertRaises(ProtectedError):
            producto.categoria.delete()

    def test_no_se_puede_borrar_una_marca_con_productos(self):
        marca = Marca.objects.create(nombre="Samsung")
        crear_producto(marca=marca)
        with self.assertRaises(ProtectedError):
            marca.delete()

    def test_str_devuelve_el_nombre(self):
        self.assertEqual(str(crear_producto(nombre="Cargador")), "Cargador")


class ActivoPorDefectoTests(TestCase):
    """Nada se borra, se desactiva: todo arranca activo."""

    def test_todo_arranca_activo(self):
        marca = Marca.objects.create(nombre="Samsung")
        categoria_rep = CategoriaReparacion.objects.create(nombre="Módulo")
        casos = {
            "CategoriaProducto": CategoriaProducto.objects.create(nombre="Cables").activa,
            "Marca": marca.activa,
            "Producto": crear_producto().activo,
            "ModeloEquipo": ModeloEquipo.objects.create(nombre="A22", marca=marca, tipo_id="celular").activo,
            "CategoriaReparacion": categoria_rep.activo,
            "Reparacion": Reparacion.objects.create(nombre="Cambio de módulo", categoria=categoria_rep).activo,
        }
        for nombre, activo in casos.items():
            with self.subTest(clase=nombre):
                self.assertTrue(activo)


class ClienteTelefonoTests(TestCase):
    def test_un_cliente_puede_tener_varios_telefonos(self):
        cliente = Cliente.objects.create(nombre="Juan")
        Telefono.objects.create(cliente=cliente, numero="3584000001")
        Telefono.objects.create(cliente=cliente, numero="3584000002")
        self.assertEqual(cliente.telefonos.count(), 2)

    def test_un_telefono_no_es_principal_por_defecto(self):
        cliente = Cliente.objects.create(nombre="Juan")
        telefono = Telefono.objects.create(cliente=cliente, numero="3584000001")
        self.assertFalse(telefono.principal)

    def test_borrar_un_cliente_borra_sus_telefonos(self):
        cliente = Cliente.objects.create(nombre="Juan")
        Telefono.objects.create(cliente=cliente, numero="3584000001")
        cliente.delete()
        self.assertEqual(Telefono.objects.count(), 0)

    def test_email_y_direccion_son_opcionales(self):
        cliente = Cliente(nombre="Juan")
        cliente.full_clean()  # no debe lanzar ValidationError

    def test_el_nombre_es_obligatorio(self):
        with self.assertRaises(ValidationError):
            Cliente(nombre="").full_clean()

    def test_regla_suave_el_modelo_permite_un_cliente_sin_telefono(self):
        """El bloqueo 'al menos un teléfono' ya no vive en el modelo."""
        cliente = Cliente.objects.create(nombre="Juan")
        self.assertEqual(cliente.telefonos.count(), 0)


class ModeloEquipoTests(TestCase):
    def setUp(self):
        self.marca = Marca.objects.create(nombre="Samsung")

    def test_celular_y_notebook_son_tipos_validos(self):
        for tipo in ("celular", "notebook"):
            with self.subTest(tipo=tipo):
                ModeloEquipo(nombre="X", marca=self.marca, tipo_id=tipo).full_clean()

    def test_tipo_desactivado_no_sirve_para_un_modelo(self):
        # Desde el 18/11/2026 los tipos están en una tabla (TipoEquipo): uno desactivado no se elige
        from catalogo.models import TipoEquipo
        TipoEquipo.objects.filter(clave="pc").update(activo=False)
        with self.assertRaises(ValidationError):
            ModeloEquipo(nombre="Optiplex", marca=self.marca, tipo_id="pc").full_clean()
        with self.assertRaises(ValidationError):
            ModeloEquipo(nombre="Optiplex", marca=self.marca, tipo_id="no-existe").full_clean()

    def test_no_se_puede_borrar_una_marca_con_modelos(self):
        ModeloEquipo.objects.create(nombre="A22", marca=self.marca, tipo_id="celular")
        with self.assertRaises(ProtectedError):
            self.marca.delete()

    def test_str_incluye_la_marca_y_el_nombre(self):
        modelo = ModeloEquipo.objects.create(nombre="A22 5G", marca=self.marca, tipo_id="celular")
        self.assertIn("A22 5G", str(modelo))
        self.assertIn("Samsung", str(modelo))


class ReparacionCatalogoTests(TestCase):
    def setUp(self):
        self.categoria = CategoriaReparacion.objects.create(nombre="Módulo")

    def test_la_categoria_es_obligatoria(self):
        with self.assertRaises(ValidationError):
            Reparacion(nombre="Cambio de módulo OLED").full_clean()

    def test_varias_reparaciones_comparten_categoria(self):
        Reparacion.objects.create(nombre="Módulo OLED", categoria=self.categoria)
        Reparacion.objects.create(nombre="Módulo económico", categoria=self.categoria)
        self.assertEqual(Reparacion.objects.filter(categoria=self.categoria).count(), 2)

    def test_no_se_puede_borrar_una_categoria_con_reparaciones(self):
        Reparacion.objects.create(nombre="Módulo OLED", categoria=self.categoria)
        with self.assertRaises(ProtectedError):
            self.categoria.delete()


class AdminCatalogoTests(TestCase):
    """Pantallas del admin de la etapa 1 (incluye tests de regresión)."""

    MODELOS = [
        "categoriaproducto", "marca", "producto", "cliente",
        "modeloequipo", "categoriareparacion", "reparacion",
    ]

    def setUp(self):
        usuario = get_user_model().objects.create_superuser("admin_test", "a@a.com", "clave123")
        self.client.force_login(usuario)
        marca = Marca.objects.create(nombre="Samsung")
        crear_producto(marca=marca)
        cliente = Cliente.objects.create(nombre="Juan")
        Telefono.objects.create(cliente=cliente, numero="3584000001")
        ModeloEquipo.objects.create(nombre="A22", marca=marca, tipo_id="celular")
        categoria = CategoriaReparacion.objects.create(nombre="Módulo")
        Reparacion.objects.create(nombre="Módulo OLED", categoria=categoria)

    def test_las_verificaciones_del_sistema_pasan(self):
        call_command("check")

    def test_cada_listado_responde(self):
        for modelo in self.MODELOS:
            with self.subTest(modelo=modelo):
                url = reverse(f"admin:catalogo_{modelo}_changelist")
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_cada_pantalla_de_alta_responde(self):
        for modelo in self.MODELOS:
            with self.subTest(modelo=modelo):
                url = reverse(f"admin:catalogo_{modelo}_add")
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_la_busqueda_de_cada_listado_no_se_rompe(self):
        """Regresión: buscar en Reparacion por 'categoria' daba FieldError."""
        for modelo in self.MODELOS:
            with self.subTest(modelo=modelo):
                url = reverse(f"admin:catalogo_{modelo}_changelist")
                self.assertEqual(self.client.get(url, {"q": "a"}).status_code, 200)

    def test_buscar_una_reparacion_por_el_nombre_de_su_categoria(self):
        url = reverse("admin:catalogo_reparacion_changelist")
        respuesta = self.client.get(url, {"q": "Módulo"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Módulo OLED")