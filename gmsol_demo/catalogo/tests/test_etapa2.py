"""Tests de la etapa 2: orden de trabajo (módulo 2).

Correr solo este archivo:
    python manage.py test catalogo.tests.test_etapa2_orden

Los valores esperados del estado de la orden salen de lo acordado en el .md
(GMSol-diagrama-clases-v4.md). Si en tu código usás otras palabras para el
estado de la orden, cambialas en estas tres constantes.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogo.models import (
    CategoriaProducto,
    CategoriaReparacion,
    Cliente,
    EquipoRecibido,
    LineaProducto,
    LineaReparacion,
    Marca,
    ModeloEquipo,
    OrdenTrabajo,
    Producto,
    Reparacion,
    Telefono,
)

EN_REPARACION = "pendiente"      # algún equipo pendiente (o la orden no tiene equipos)
LISTA = "listo"                  # nada pendiente y al menos uno resuelto
NO_ARREGLABLE = "no_arreglable"  # todos los equipos sin arreglo


def crear_orden(nombre_cliente="Juan"):
    cliente = Cliente.objects.create(nombre=nombre_cliente)
    return OrdenTrabajo.objects.create(cliente=cliente)


def crear_equipo(orden, estado="pendiente", tipo="celular", modelo=None):
    return EquipoRecibido.objects.create(
        orden_trabajo=orden,
        tipo=tipo,
        modelo=modelo,
        problema="no carga",
        tipo_bloqueo="ninguno",
        estado=estado,
    )


def crear_reparacion(nombre="Cambio de módulo OLED"):
    categoria, _ = CategoriaReparacion.objects.get_or_create(nombre="Módulo")
    return Reparacion.objects.create(nombre=nombre, categoria=categoria)


def crear_producto(precio_venta="1500.00"):
    categoria, _ = CategoriaProducto.objects.get_or_create(nombre="Cables")
    return Producto.objects.create(
        nombre="Cable USB-C",
        categoria=categoria,
        precio_compra=Decimal("1000.00"),
        precio_venta=Decimal(precio_venta),
    )


class OrdenTests(TestCase):
    def test_el_numero_de_orden_es_automatico(self):
        primera = crear_orden("Ana")
        segunda = crear_orden("Luis")
        self.assertIsNotNone(primera.id)
        self.assertGreater(segunda.id, primera.id)

    def test_la_fecha_de_recepcion_se_completa_sola(self):
        self.assertIsNotNone(crear_orden().fecha_recepcion)

    def test_la_fecha_de_recepcion_no_acepta_fechas_pasadas(self):
        cliente = Cliente.objects.create(nombre="Juan")
        hace_un_mes = timezone.now() - timedelta(days=30)
        orden = OrdenTrabajo.objects.create(cliente=cliente, fecha_recepcion=hace_un_mes)
        self.assertGreater(orden.fecha_recepcion, hace_un_mes + timedelta(days=29))

    def test_el_cliente_conoce_sus_ordenes(self):
        orden = crear_orden()
        self.assertEqual(orden.cliente.ordenes.count(), 1)

    def test_no_se_puede_borrar_un_cliente_con_ordenes(self):
        orden = crear_orden()
        with self.assertRaises(ProtectedError):
            orden.cliente.delete()

    def test_el_estado_de_la_orden_no_es_un_campo_guardado(self):
        campos = [campo.name for campo in OrdenTrabajo._meta.get_fields()]
        self.assertNotIn("estado", campos)

    def test_borrar_una_orden_borra_sus_equipos_y_lineas(self):
        orden = crear_orden()
        equipo = crear_equipo(orden)
        LineaReparacion.objects.create(
            equipo=equipo, reparacion=crear_reparacion(), precio_en_orden=Decimal("45000.00")
        )
        LineaProducto.objects.create(
            orden_trabajo=orden, producto=crear_producto(),
            cantidad_adquirida=1, precio_en_orden=Decimal("1500.00"),
        )
        orden.delete()
        self.assertEqual(EquipoRecibido.objects.count(), 0)
        self.assertEqual(LineaReparacion.objects.count(), 0)
        self.assertEqual(LineaProducto.objects.count(), 0)


class EquipoRecibidoTests(TestCase):
    def setUp(self):
        self.orden = crear_orden()

    def test_una_pc_se_guarda_sin_modelo(self):
        equipo = crear_equipo(self.orden, tipo="pc", modelo=None)
        equipo.full_clean()
        self.assertIsNone(equipo.modelo)

    def test_tipos_de_equipo_validos_e_invalido(self):
        for tipo in ("celular", "notebook", "pc"):
            with self.subTest(tipo=tipo):
                crear_equipo(self.orden, tipo=tipo).full_clean()
        with self.assertRaises(ValidationError):
            crear_equipo(self.orden, tipo="tablet").full_clean()

    def test_el_estado_arranca_pendiente(self):
        equipo = EquipoRecibido.objects.create(
            orden_trabajo=self.orden, tipo="celular", problema="no carga", tipo_bloqueo="pin"
        )
        self.assertEqual(equipo.estado, "pendiente")

    def test_estados_validos_e_invalido(self):
        for estado in ("pendiente", "arreglado", "no_arreglable", "sin_falla"):
            with self.subTest(estado=estado):
                crear_equipo(self.orden, estado=estado).full_clean()
        with self.assertRaises(ValidationError):
            crear_equipo(self.orden, estado="roto").full_clean()

    def test_tipos_de_bloqueo_validos_e_invalido(self):
        for bloqueo in ("pin", "patron", "contrasena", "ninguno"):
            with self.subTest(bloqueo=bloqueo):
                equipo = crear_equipo(self.orden)
                equipo.tipo_bloqueo = bloqueo
                equipo.full_clean()
        equipo.tipo_bloqueo = "huella"
        with self.assertRaises(ValidationError):
            equipo.full_clean()

    def test_clave_y_accesorios_son_opcionales(self):
        equipo = crear_equipo(self.orden)
        self.assertEqual(equipo.clave_bloqueo, "")
        self.assertEqual(equipo.accesorios_dejados, "")
        equipo.full_clean()

    def test_la_clave_se_guarda_tal_cual(self):
        equipo = crear_equipo(self.orden)
        equipo.tipo_bloqueo = "patron"
        equipo.clave_bloqueo = "1-5-9-6"
        equipo.save()
        equipo.refresh_from_db()
        self.assertEqual(equipo.clave_bloqueo, "1-5-9-6")

    def test_el_problema_es_obligatorio(self):
        equipo = crear_equipo(self.orden)
        equipo.problema = ""
        with self.assertRaises(ValidationError):
            equipo.full_clean()

    def test_la_orden_conoce_sus_equipos(self):
        crear_equipo(self.orden)
        crear_equipo(self.orden, tipo="notebook")
        self.assertEqual(self.orden.equipos.count(), 2)

    def test_no_se_puede_borrar_un_modelo_con_equipos(self):
        marca = Marca.objects.create(nombre="Samsung")
        modelo = ModeloEquipo.objects.create(nombre="A22", marca=marca, tipo="celular")
        crear_equipo(self.orden, modelo=modelo)
        with self.assertRaises(ProtectedError):
            modelo.delete()


class EstadoOrdenTests(TestCase):
    """El estado de la orden se calcula a partir del estado de sus equipos."""

    CASOS = [
        ([], EN_REPARACION),
        (["pendiente"], EN_REPARACION),
        (["pendiente", "arreglado"], EN_REPARACION),
        (["pendiente", "no_arreglable"], EN_REPARACION),
        (["pendiente", "sin_falla"], EN_REPARACION),
        (["arreglado"], LISTA),
        (["sin_falla"], LISTA),
        (["arreglado", "arreglado"], LISTA),
        (["arreglado", "no_arreglable"], LISTA),
        (["no_arreglable", "sin_falla"], LISTA),
        (["no_arreglable"], NO_ARREGLABLE),
        (["no_arreglable", "no_arreglable"], NO_ARREGLABLE),
    ]

    def test_estado_de_la_orden_segun_sus_equipos(self):
        for estados, esperado in self.CASOS:
            with self.subTest(equipos=estados):
                orden = crear_orden()
                for estado in estados:
                    crear_equipo(orden, estado=estado)
                self.assertEqual(orden.estado, esperado)

    def test_el_estado_cambia_cuando_cambia_un_equipo(self):
        orden = crear_orden()
        equipo = crear_equipo(orden, estado="pendiente")
        self.assertEqual(orden.estado, EN_REPARACION)
        equipo.estado = "arreglado"
        equipo.save()
        self.assertEqual(OrdenTrabajo.objects.get(pk=orden.pk).estado, LISTA)


class LineaReparacionTests(TestCase):
    def setUp(self):
        self.equipo = crear_equipo(crear_orden())
        self.reparacion = crear_reparacion()

    def crear_linea(self, precio="45000.00"):
        return LineaReparacion.objects.create(
            equipo=self.equipo, reparacion=self.reparacion, precio_en_orden=Decimal(precio)
        )

    def test_el_subtotal_es_el_precio(self):
        self.assertEqual(self.crear_linea("45000.00").subtotal, Decimal("45000.00"))

    def test_un_precio_negativo_no_es_valido(self):
        linea = self.crear_linea()
        linea.precio_en_orden = Decimal("-1.00")
        with self.assertRaises(ValidationError):
            linea.full_clean()

    def test_un_precio_cero_es_valido(self):
        """Sirve para 'Revisión / diagnóstico' sin cargo."""
        linea = self.crear_linea()
        linea.precio_en_orden = Decimal("0.00")
        linea.full_clean()

    def test_la_nota_es_opcional(self):
        self.crear_linea().full_clean()

    def test_el_equipo_conoce_sus_lineas(self):
        self.crear_linea()
        self.crear_linea("1000.00")
        self.assertEqual(self.equipo.lineas_reparacion.count(), 2)

    def test_no_se_puede_borrar_una_reparacion_usada(self):
        self.crear_linea()
        with self.assertRaises(ProtectedError):
            self.reparacion.delete()


class LineaProductoTests(TestCase):
    def setUp(self):
        self.orden = crear_orden()
        self.producto = crear_producto("1500.00")

    def crear_linea(self, cantidad=3, precio="1500.00", producto=None):
        return LineaProducto.objects.create(
            orden_trabajo=self.orden,
            producto=producto or self.producto,
            cantidad_adquirida=cantidad,
            precio_en_orden=Decimal(precio),
        )

    def test_subtotal_es_cantidad_por_precio(self):
        self.assertEqual(self.crear_linea(3, "1500.00").subtotal, Decimal("4500.00"))

    def test_subtotal_de_una_linea_vacia_no_rompe(self):
        """Regresión: la fila vacía del admin rompía la pantalla de alta."""
        self.assertIn(LineaProducto().subtotal, (None, 0))

    def test_la_cantidad_cero_no_es_valida(self):
        linea = self.crear_linea()
        linea.cantidad_adquirida = 0
        with self.assertRaises(ValidationError):
            linea.full_clean()

    def test_la_cantidad_uno_es_valida(self):
        linea = self.crear_linea()
        linea.cantidad_adquirida = 1
        linea.full_clean()

    def test_un_precio_negativo_no_es_valido(self):
        linea = self.crear_linea()
        linea.precio_en_orden = Decimal("-5.00")
        with self.assertRaises(ValidationError):
            linea.full_clean()

    def test_el_precio_de_la_linea_se_conserva_si_cambia_el_producto(self):
        linea = self.crear_linea(1, "1500.00")
        self.producto.precio_venta = Decimal("2000.00")
        self.producto.save()
        linea.refresh_from_db()
        self.assertEqual(linea.precio_en_orden, Decimal("1500.00"))

    def test_no_se_puede_borrar_un_producto_usado(self):
        self.crear_linea()
        with self.assertRaises(ProtectedError):
            self.producto.delete()

    def test_una_orden_puede_tener_varios_productos(self):
        otro = Producto.objects.create(
            nombre="Templado", categoria=self.producto.categoria,
            precio_compra=Decimal("500.00"), precio_venta=Decimal("900.00"),
        )
        self.crear_linea(2, "1500.00")
        self.crear_linea(1, "900.00", producto=otro)
        self.assertEqual(self.orden.lineas_producto.count(), 2)
        total = sum(linea.subtotal for linea in self.orden.lineas_producto.all())
        self.assertEqual(total, Decimal("3900.00"))


class AdminOrdenTests(TestCase):
    """Pantallas del admin de la etapa 2 (incluye tests de regresión)."""

    def setUp(self):
        usuario = get_user_model().objects.create_superuser("admin_test", "a@a.com", "clave123")
        self.client.force_login(usuario)
        self.orden = crear_orden()
        Telefono.objects.create(cliente=self.orden.cliente, numero="3584000001")

    def datos_de_alta(self, con_equipo):
        datos = {
            "cliente": self.orden.cliente.id,
            "equipos-TOTAL_FORMS": "1", "equipos-INITIAL_FORMS": "0",
            "equipos-MIN_NUM_FORMS": "0", "equipos-MAX_NUM_FORMS": "1000",
            "lineas_producto-TOTAL_FORMS": "0", "lineas_producto-INITIAL_FORMS": "0",
            "lineas_producto-MIN_NUM_FORMS": "0", "lineas_producto-MAX_NUM_FORMS": "1000",
        }
        if con_equipo:
            datos.update({
                "equipos-0-tipo": "pc",
                "equipos-0-problema": "no enciende",
                "equipos-0-tipo_bloqueo": "ninguno",
                "equipos-0-estado": "pendiente",
            })
        return datos

    def test_la_pantalla_de_alta_de_orden_carga(self):
        """Regresión: el subtotal de la fila vacía daba error 500."""
        url = reverse("admin:catalogo_ordentrabajo_add")
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_la_edicion_de_una_orden_con_lineas_carga(self):
        crear_equipo(self.orden)
        LineaProducto.objects.create(
            orden_trabajo=self.orden, producto=crear_producto(),
            cantidad_adquirida=2, precio_en_orden=Decimal("1500.00"),
        )
        url = reverse("admin:catalogo_ordentrabajo_change", args=[self.orden.id])
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_una_orden_sin_equipos_no_se_guarda(self):
        antes = OrdenTrabajo.objects.count()
        url = reverse("admin:catalogo_ordentrabajo_add")
        respuesta = self.client.post(url, self.datos_de_alta(con_equipo=False))
        self.assertEqual(respuesta.status_code, 200)  # vuelve al formulario con el error
        self.assertEqual(OrdenTrabajo.objects.count(), antes)

    def test_una_orden_con_un_equipo_se_guarda(self):
        antes = OrdenTrabajo.objects.count()
        url = reverse("admin:catalogo_ordentrabajo_add")
        respuesta = self.client.post(url, self.datos_de_alta(con_equipo=True))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(OrdenTrabajo.objects.count(), antes + 1)
        self.assertEqual(EquipoRecibido.objects.filter(tipo="pc").count(), 1)

    def test_listados_y_busquedas_responden(self):
        for modelo in ("ordentrabajo", "lineareparacion", "lineaproducto"):
            with self.subTest(modelo=modelo):
                url = reverse(f"admin:catalogo_{modelo}_changelist")
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(self.client.get(url, {"q": "a"}).status_code, 200)