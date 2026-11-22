from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from negocio.models import (
    CategoriaReparacion, Cliente, Devolucion, EquipoRecibido, LineaReparacion, Marca, MetodoPago,
    ModeloEquipo, OrdenTrabajo, Pago, Reparacion,
)
from negocio.servicios import cerrar_orden
from web.templatetags.formato import pesos, pista

D = Decimal


class DatosBase(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("papa", password="clave-segura-123")
        self.efectivo = MetodoPago.objects.create(nombre="Efectivo", cuenta="efectivo")
        self.juan = Cliente.objects.create(nombre="Juan Pérez")
        marca = Marca.objects.create(nombre="Samsung")
        self.modelo = ModeloEquipo.objects.create(nombre="Galaxy A14", marca=marca, tipo_id="celular")
        self.reparacion = Reparacion.objects.create(
            nombre="Módulo OLED", categoria=CategoriaReparacion.objects.create(nombre="Módulo"))

    def orden(self, precio="1000", estado="pendiente", pagado=None, modelo=True):
        o = OrdenTrabajo.objects.create(cliente=self.juan)
        e = EquipoRecibido.objects.create(
            orden_trabajo=o, tipo_id="celular", problema="x", modelo=self.modelo if modelo else None)
        LineaReparacion.objects.create(equipo=e, reparacion=self.reparacion, precio_vendido=D(precio))
        if pagado:
            Pago.objects.create(orden_trabajo=o, metodo_pago=self.efectivo, monto=D(pagado))
        if estado != "pendiente":
            e.estado = estado
            e.save()
        return o

    def entrar(self):
        self.client.login(username="papa", password="clave-segura-123")


class AccesoTests(DatosBase):
    def test_sin_login_manda_al_ingreso(self):
        r = self.client.get(reverse("web:inicio"))
        self.assertRedirects(r, "/login/?next=/")

    def test_pantalla_de_ingreso(self):
        r = self.client.get(reverse("web:login"))
        self.assertContains(r, "Ingresar")
        self.assertContains(r, "logo.webp")

    def test_ingresar_con_clave_correcta(self):
        r = self.client.post(reverse("web:login"), {"username": "papa", "password": "clave-segura-123"})
        self.assertRedirects(r, reverse("web:inicio"))

    def test_clave_incorrecta(self):
        r = self.client.post(reverse("web:login"), {"username": "papa", "password": "mala"})
        self.assertContains(r, "Usuario o contraseña incorrectos.")

    def test_cerrar_sesion(self):
        self.entrar()
        r = self.client.post(reverse("web:logout"))
        self.assertRedirects(r, reverse("web:login"))
        self.assertEqual(self.client.get(reverse("web:inicio")).status_code, 302)


class InicioTests(DatosBase):
    def setUp(self):
        super().setUp()
        self.entrar()

    def test_estructura_base(self):
        r = self.client.get(reverse("web:inicio"))
        self.assertEqual(r.status_code, 200)
        for texto in ("Órdenes de trabajo", "Devoluciones", "Facturación ARCA", "Cerrar sesión",
                      "Nueva orden", "Venta rápida", "Entregar equipo", "logo.webp", "gmsol.css", "Saltar al contenido"):
            self.assertContains(r, texto)

    def test_vacio(self):
        r = self.client.get(reverse("web:inicio"))
        self.assertContains(r, "No hay órdenes en curso.")

    def test_muestra_ordenes_en_curso_con_estado_y_saldo(self):
        en_revision = self.orden("42500")
        lista = self.orden("20000", estado="arreglado", pagado="20000")
        r = self.client.get(reverse("web:inicio"))
        self.assertContains(r, f"#{en_revision.id}")
        self.assertContains(r, "En revisión / reparación")
        self.assertContains(r, "Debe $ 42.500")
        self.assertContains(r, f"#{lista.id}")
        self.assertContains(r, "Saldado")
        self.assertContains(r, "Galaxy A14")
        self.assertContains(r, "Juan Pérez")

    def test_los_conteos(self):
        self.orden("1000")                                        # en revisión
        self.orden("1000", estado="arreglado", pagado="1000")     # lista
        self.orden("1000", estado="arreglado", pagado="1000")     # lista
        r = self.client.get(reverse("web:inicio"))
        self.assertEqual((r.context["en_revision"], r.context["listas"], r.context["devoluciones"]), (1, 2, 0))

    def test_no_arreglable_con_dinero_a_devolver(self):
        o = self.orden("55000", pagado="10000", estado="no_arreglable")
        Devolucion.objects.create(orden_trabajo=o, monto=D("10000"))
        r = self.client.get(reverse("web:inicio"))
        self.assertContains(r, "No arreglable")
        self.assertContains(r, "A favor: $ 10.000 (devolver)")
        self.assertEqual(r.context["devoluciones"], 1)

    def test_no_aparecen_las_cerradas(self):
        cerrada = self.orden("1000", estado="arreglado", pagado="1000")
        cerrar_orden(cerrada)
        r = self.client.get(reverse("web:inicio"))
        self.assertNotContains(r, f"#{cerrada.id}<")
        self.assertContains(r, "No hay órdenes en curso.")
        # Sin arreglo y sin seña sigue en curso hasta devolverle el equipo (regla del 18/11/2026)
        finalizada = self.orden("1000", estado="no_arreglable")
        self.assertContains(self.client.get(reverse("web:inicio")), f"#{finalizada.id}<")

    def test_devolucion_ya_hecha_no_cuenta(self):
        o = self.orden("1000", pagado="400", estado="no_arreglable")
        Devolucion.objects.create(orden_trabajo=o, monto=D("400"), metodo_pago=self.efectivo)
        self.assertEqual(self.client.get(reverse("web:inicio")).context["devoluciones"], 0)

    def test_equipo_sin_modelo_y_varios_equipos(self):
        o = self.orden("1000", modelo=False)
        EquipoRecibido.objects.create(orden_trabajo=o, tipo_id="pc", problema="y")
        r = self.client.get(reverse("web:inicio"))
        self.assertContains(r, "Celular + 1 más")

    def test_diseno_v2_y_fecha(self):
        r = self.client.get(reverse("web:inicio"))
        self.assertContains(r, "gmsol.css")
        self.assertNotContains(r, "fonts.googleapis.com")      # fuentes alojadas en el proyecto
        self.assertContains(r, 'class="fecha"')

    def test_pista_de_progreso_en_la_tabla(self):
        self.orden("1000")                                        # en revisión
        self.orden("1000", estado="arreglado", pagado="1000")     # lista
        r = self.client.get(reverse("web:inicio"))
        self.assertContains(r, 'class="pista wip"')
        self.assertContains(r, 'class="pista ok"')
        self.assertContains(r, 'class="n actual"', count=2)

    def test_a_favor_se_marca_en_rojo(self):
        self.orden("55000", pagado="10000", estado="no_arreglable")
        r = self.client.get(reverse("web:inicio"))
        self.assertContains(r, 'class="der afavor"')

    def test_cantidad_de_consultas_no_crece_con_las_ordenes(self):
        self.orden("1000")
        with CaptureQueriesContext(connection) as pocas:
            self.client.get(reverse("web:inicio"))
        for _ in range(6):
            self.orden("1000", pagado="100")
        with CaptureQueriesContext(connection) as muchas:
            self.client.get(reverse("web:inicio"))
        self.assertEqual(len(pocas), len(muchas))


class FormatoTests(TestCase):
    def test_pesos(self):
        self.assertEqual(pesos(42500), "$ 42.500")
        self.assertEqual(pesos(D("1234.5")), "$ 1.234,50")
        self.assertEqual(pesos(D("-10000.00")), "$ 10.000")
        self.assertEqual(pesos(0), "$ 0")


class PistaTests(DatosBase):
    """La pista: Recibida · Revisión · Lista · Entregada."""

    def test_en_revision(self):
        self.assertEqual(pista(self.orden()), ["hecho", "actual", "", ""])

    def test_lista(self):
        self.assertEqual(pista(self.orden(estado="arreglado")), ["hecho", "hecho", "actual", ""])

    def test_no_arreglable_queda_en_el_paso_de_lista(self):
        o = self.orden(pagado="500", estado="no_arreglable")
        self.assertEqual(pista(o), ["hecho", "hecho", "actual", ""])

    def test_cerrada_llega_al_final(self):
        o = self.orden(estado="arreglado", pagado="1000")
        cerrar_orden(o)
        o = OrdenTrabajo.objects.get(pk=o.pk)
        self.assertEqual(pista(o), ["hecho", "hecho", "hecho", "actual"])
