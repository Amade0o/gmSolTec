"""Tests de las pantallas Caja, Movimiento e Historial (etapa 4, paso 4.1).

Comprueban lo que ve y hace el dueño: que pida login, que los botones hagan lo que dicen, que los
errores se muestren y que no se guarde nada de más.

Correr solo este archivo:
    python manage.py test web.tests.test_caja_pantallas
"""
from datetime import datetime
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from negocio import servicios
from negocio.models import Cambio, MovimientoCaja

D = Decimal


class BaseCaja(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("papa", password="clave-segura-123")
        self.client.force_login(self.usuario)


class PideLoginTests(TestCase):
    def test_las_pantallas_de_caja_piden_login(self):
        mov = MovimientoCaja.objects.create(caja="efectivo", tipo="cobro", monto=D("10"), descripcion="x")
        for url in (reverse("web:caja"), reverse("web:movimiento_caja", args=[mov.pk]), reverse("web:historial")):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse("web:login"), respuesta["Location"])


class PantallaCajaTests(BaseCaja):
    def test_muestra_los_saldos_de_cada_caja(self):
        servicios.cargar_saldo_inicial("efectivo", D("150000"))
        servicios.cargar_saldo_inicial("digital", D("420000"))
        MovimientoCaja.objects.create(caja="senas_efectivo", tipo="sena", monto=D("5000"), descripcion="Seña orden #1")

        html = self.client.get(reverse("web:caja")).content.decode()

        self.assertIn("$ 150.000", html)
        self.assertIn("$ 420.000", html)
        self.assertIn("En efectivo: $ 5.000", html)
        self.assertIn("En digital: $ 0", html)

    def test_esta_en_el_menu_y_ya_no_figura_como_proximamente(self):
        html = self.client.get(reverse("web:inicio")).content.decode()

        self.assertIn(f'href="{reverse("web:caja")}"', html)
        self.assertIn(f'href="{reverse("web:historial")}"', html)
        self.assertNotIn('<span class="t">Caja</span><span class="tag">pronto</span>', html)

    def test_cargar_el_saldo_inicial(self):
        respuesta = self.client.post(reverse("web:caja"), {
            "accion": "saldo_inicial", "caja": "efectivo", "monto": "150000", "nota": "Contado"})

        self.assertRedirects(respuesta, reverse("web:caja"))
        self.assertEqual(servicios.saldo_de("efectivo"), D("150000"))
        mensajes = [str(m) for m in respuesta.wsgi_request._messages]
        self.assertIn("Listo: el saldo inicial de Efectivo es $ 150.000.", mensajes)

    def test_el_boton_pide_confirmacion_repitiendo_monto_y_caja(self):
        html = self.client.get(reverse("web:caja")).content.decode()

        self.assertIn('data-confirmar="¿Guardar {monto} como saldo inicial de {caja}?"', html)

    def test_sin_monto_no_se_guarda_y_muestra_el_error(self):
        respuesta = self.client.post(reverse("web:caja"), {"accion": "saldo_inicial", "caja": "efectivo", "monto": ""})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'class="error"')
        self.assertFalse(MovimientoCaja.objects.exists())

    def test_si_la_regla_rechaza_el_saldo_inicial_se_muestra_el_aviso(self):
        # Caso raro (por ejemplo, se cargó en otra pestaña al mismo tiempo): el servicio decide
        with mock.patch("negocio.servicios.cargar_saldo_inicial",
                        side_effect=servicios.ReglaDeNegocioError("Efectivo ya tiene saldo inicial.")):
            respuesta = self.client.post(reverse("web:caja"), {"accion": "saldo_inicial", "caja": "efectivo", "monto": "5"})

        self.assertContains(respuesta, "Efectivo ya tiene saldo inicial.")
        self.assertFalse(MovimientoCaja.objects.exists())

    def test_la_caja_que_ya_tiene_saldo_inicial_no_se_ofrece_de_nuevo(self):
        servicios.cargar_saldo_inicial("efectivo", D("1000"))

        respuesta = self.client.post(reverse("web:caja"), {"accion": "saldo_inicial", "caja": "efectivo", "monto": "5"})

        self.assertEqual(respuesta.status_code, 200)        # no es una opción válida del formulario
        self.assertEqual(servicios.saldo_de("efectivo"), D("1000"))

    def test_con_las_dos_cajas_cargadas_ya_no_aparece_el_formulario(self):
        servicios.cargar_saldo_inicial("efectivo", D("1000"))
        servicios.cargar_saldo_inicial("digital", D("1000"))

        html = self.client.get(reverse("web:caja")).content.decode()

        self.assertNotIn("Guardar el saldo inicial", html)

    def test_filtrar_por_caja_muestra_solo_esa(self):
        servicios.cargar_saldo_inicial("efectivo", D("1000"))
        servicios.cargar_saldo_inicial("digital", D("2000"))

        html = self.client.get(reverse("web:caja") + "?caja=digital").content.decode()

        self.assertIn("Saldo inicial de Digital", html)
        self.assertNotIn("Saldo inicial de Efectivo", html)

    def test_un_filtro_que_no_existe_muestra_todas(self):
        servicios.cargar_saldo_inicial("efectivo", D("1000"))

        html = self.client.get(reverse("web:caja") + "?caja=inventada").content.decode()

        self.assertIn("Saldo inicial de Efectivo", html)

    def test_lo_anulado_se_ve_tachado(self):
        servicios.anular_movimiento(servicios.cargar_saldo_inicial("efectivo", D("1000")))

        html = self.client.get(reverse("web:caja")).content.decode()

        self.assertIn('<tr class="tachado">', html)
        self.assertIn("(anulado)", html)

    def test_entradas_y_salidas_van_en_columnas_distintas_sin_signo_menos(self):
        servicios.cargar_saldo_inicial("efectivo", D("1000"))
        servicios.registrar_movimiento("efectivo", "retiro", D("-250"), "Retiro del dueño")

        html = self.client.get(reverse("web:caja")).content.decode()

        self.assertIn('<td class="der sale" data-label="Sale">$ 250</td>', html)
        self.assertNotIn("-250", html)


class PantallaMovimientoTests(BaseCaja):
    def setUp(self):
        super().setUp()
        self.inicial = servicios.cargar_saldo_inicial("efectivo", D("1000"))
        self.url = reverse("web:movimiento_caja", args=[self.inicial.pk])

    def test_corregir_cambia_el_monto_y_lo_deja_en_el_historial(self):
        respuesta = self.client.post(self.url, {"accion": "corregir", "monto": "1200", "nota": ""})

        self.assertRedirects(respuesta, self.url)
        self.assertEqual(servicios.saldo_de("efectivo"), D("1200"))
        self.assertContains(self.client.get(self.url), "de $ 1.000 a $ 1.200")

    def test_corregir_con_un_error_de_regla_muestra_el_aviso(self):
        servicios.registrar_movimiento("efectivo", "retiro", D("-900"), "Retiro")

        respuesta = self.client.post(self.url, {"accion": "corregir", "monto": "100", "nota": ""}, follow=True)

        self.assertContains(respuesta, "quedaría en negativo")
        self.assertEqual(servicios.saldo_de("efectivo"), D("100"))

    def test_anular_lo_tacha_y_vuelve_a_la_caja(self):
        respuesta = self.client.post(self.url, {"accion": "anular", "motivo": "Era de prueba"})

        self.assertRedirects(respuesta, reverse("web:caja"))
        self.inicial.refresh_from_db()
        self.assertTrue(self.inicial.anulado)
        self.assertContains(self.client.get(self.url), "Motivo: Era de prueba")

    def test_un_anulado_ya_no_ofrece_corregir_ni_anular(self):
        servicios.anular_movimiento(self.inicial)

        html = self.client.get(self.url).content.decode()

        self.assertNotIn("Guardar la corrección", html)
        self.assertNotIn("Anular este movimiento", html)

    def test_lo_que_no_se_cargo_a_mano_no_se_toca_desde_aca(self):
        cobro = MovimientoCaja.objects.create(caja="efectivo", tipo="cobro", monto=D("300"), descripcion="Venta #4")
        url = reverse("web:movimiento_caja", args=[cobro.pk])

        html = self.client.get(url).content.decode()
        self.client.post(url, {"accion": "corregir", "monto": "999"})

        self.assertIn("se corrige desde ahí", html)
        self.assertNotIn("Guardar la corrección", html)
        cobro.refresh_from_db()
        self.assertEqual(cobro.monto, D("300"))

    def test_corregir_sin_monto_muestra_el_error_y_no_cambia_nada(self):
        respuesta = self.client.post(self.url, {"accion": "corregir", "monto": "", "nota": ""})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'class="error"')
        self.inicial.refresh_from_db()
        self.assertEqual(self.inicial.monto, D("1000"))

    def test_anular_con_un_motivo_demasiado_largo_no_anula(self):
        respuesta = self.client.post(self.url, {"accion": "anular", "motivo": "x" * 201})

        self.assertEqual(respuesta.status_code, 200)
        self.inicial.refresh_from_db()
        self.assertFalse(self.inicial.anulado)

    def test_anular_cuando_la_caja_quedaria_en_negativo_muestra_el_aviso(self):
        servicios.registrar_movimiento("efectivo", "retiro", D("-500"), "Retiro")

        respuesta = self.client.post(self.url, {"accion": "anular", "motivo": ""}, follow=True)

        self.assertContains(respuesta, "quedaría en negativo")
        self.inicial.refresh_from_db()
        self.assertFalse(self.inicial.anulado)

    def test_una_accion_desconocida_no_cambia_nada(self):
        respuesta = self.client.post(self.url, {"accion": "borrar", "monto": "5"})

        self.assertEqual(respuesta.status_code, 200)
        self.inicial.refresh_from_db()
        self.assertEqual((self.inicial.monto, self.inicial.anulado), (D("1000"), False))

    def test_un_movimiento_que_no_existe_da_404(self):
        self.assertEqual(self.client.get(reverse("web:movimiento_caja", args=[99999])).status_code, 404)


class PantallaHistorialTests(BaseCaja):
    def test_muestra_las_frases(self):
        servicios.cargar_saldo_inicial("efectivo", D("1000"))

        self.assertContains(self.client.get(reverse("web:historial")), "Cargaste el saldo inicial de Efectivo: $ 1.000.")

    def test_filtrar_por_tema(self):
        servicios.cargar_saldo_inicial("efectivo", D("1000"))

        html = self.client.get(reverse("web:historial") + "?area=stock").content.decode()

        self.assertNotIn("Cargaste el saldo inicial", html)
        self.assertIn("No hay cambios en este período.", html)

    def test_un_periodo_que_no_existe_usa_los_ultimos_7_dias(self):
        servicios.cargar_saldo_inicial("efectivo", D("1000"))

        html = self.client.get(reverse("web:historial") + "?periodo=inventado").content.decode()

        self.assertIn("Cargaste el saldo inicial", html)
        self.assertIn('aria-current="page">Últimos 7 días', html)

    def test_los_cambios_del_mismo_dia_van_juntos_y_los_de_otro_dia_aparte(self):
        zona = ZoneInfo("America/Argentina/Cordoba")
        for hora, dia in ((9, 18), (17, 18), (10, 19)):
            Cambio.objects.create(area="dinero", accion="alta", frase=f"Cambio {dia} {hora}",
                                  fecha=datetime(2026, 11, dia, hora, 0, tzinfo=zona))

        dias = self.client.get(reverse("web:historial") + "?periodo=todo").context["dias"]

        self.assertEqual([(d.day, len(cambios)) for d, cambios in dias], [(19, 1), (18, 2)])

    def test_lo_de_la_noche_queda_en_su_dia_de_argentina(self):
        # 23:30 del 20/11 en Argentina = 02:30 del 21/11 en UTC
        noche = datetime(2026, 11, 20, 23, 30, tzinfo=ZoneInfo("America/Argentina/Cordoba"))
        Cambio.objects.create(area="dinero", accion="alta", frase="Algo de la noche", fecha=noche)

        html = self.client.get(reverse("web:historial") + "?periodo=todo").content.decode()

        self.assertIn("viernes 20 de noviembre", html)
        self.assertNotIn("sábado 21 de noviembre", html)


class AdminSoloLecturaTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser("admin", password="clave-segura-123"))

    def test_la_caja_y_el_historial_se_ven_pero_no_se_cargan_desde_el_admin(self):
        for modelo in ("movimientocaja", "cambio"):
            with self.subTest(modelo=modelo):
                self.assertEqual(self.client.get(f"/admin/negocio/{modelo}/").status_code, 200)
                self.assertEqual(self.client.get(f"/admin/negocio/{modelo}/add/").status_code, 403)
