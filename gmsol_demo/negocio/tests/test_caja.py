"""Tests de la caja (etapa 4, paso 4.1): saldos, saldo inicial, corregir, anular e historial.

Cada test prueba UNA regla y sigue el patrón preparar → actuar → verificar. El nombre dice la regla.
Las reglas están en CLAUDE/DISEÑO/etapa-4-caja.md y en negocio/servicios/caja.py.

Correr solo este archivo:
    python manage.py test negocio.tests.test_caja
"""
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from negocio import servicios
from negocio.formato import pesos
from negocio.models import CAJA_CHOICES, Cambio, MovimientoCaja
from negocio.servicios import ReglaDeNegocioError

D = Decimal
CAJAS = [c for c, _ in CAJA_CHOICES]


def movimiento(caja="efectivo", tipo="cobro", monto="1000", descripcion="Movimiento de prueba", **extra):
    """Crea un movimiento directo en la base, sin pasar por los servicios (para preparar datos)."""
    return MovimientoCaja.objects.create(caja=caja, tipo=tipo, monto=D(monto), descripcion=descripcion, **extra)


# ---------- Saldo: la suma de los movimientos no anulados ----------

class SaldoTests(TestCase):
    def test_una_caja_sin_movimientos_tiene_saldo_cero(self):
        for caja in CAJAS:
            with self.subTest(caja=caja):
                self.assertEqual(servicios.saldo_de(caja), D("0.00"))

    def test_el_saldo_es_la_suma_de_los_movimientos(self):
        movimiento(monto="1000")
        movimiento(monto="2500.50")
        movimiento(tipo="devolucion", monto="-300")

        self.assertEqual(servicios.saldo_de("efectivo"), D("3200.50"))

    def test_un_movimiento_anulado_no_suma(self):
        movimiento(monto="1000")
        movimiento(monto="500", anulado=True, anulado_fecha=timezone.now())

        self.assertEqual(servicios.saldo_de("efectivo"), D("1000"))

    def test_el_saldo_de_una_caja_no_cuenta_los_de_otra(self):
        movimiento(caja="efectivo", monto="1000")
        movimiento(caja="digital", monto="7000")
        movimiento(caja="senas_efectivo", tipo="sena", monto="300")

        self.assertEqual(servicios.saldo_de("efectivo"), D("1000"))
        self.assertEqual(servicios.saldo_de("digital"), D("7000"))
        self.assertEqual(servicios.saldo_de("senas_efectivo"), D("300"))
        self.assertEqual(servicios.saldo_de("senas_digital"), D("0"))

    def test_saldos_da_lo_mismo_que_saldo_de_cada_caja(self):
        movimiento(caja="efectivo", monto="1000")
        movimiento(caja="digital", monto="250.25")
        movimiento(caja="senas_digital", tipo="sena", monto="99.99")
        movimiento(caja="efectivo", monto="10", anulado=True, anulado_fecha=timezone.now())

        todos = servicios.saldos()

        self.assertEqual(set(todos), set(CAJAS))
        for caja in CAJAS:
            with self.subTest(caja=caja):
                self.assertEqual(todos[caja], servicios.saldo_de(caja))

    def test_la_suma_de_centavos_es_exacta(self):
        # SQLite guarda los decimales como coma flotante: 0.10 + 0.20 tiene que dar 0.30 justo
        for _ in range(3):
            movimiento(monto="0.10")
        for _ in range(7):
            movimiento(monto="0.20")

        self.assertEqual(servicios.saldo_de("efectivo"), D("1.70"))

    def test_una_caja_que_no_existe_da_error(self):
        with self.assertRaises(ReglaDeNegocioError):
            servicios.saldo_de("billetera")


# ---------- Reglas de cada movimiento (modelo) ----------

class ReglasDelMovimientoTests(TestCase):
    def nuevo(self, **datos):
        base = {"caja": "efectivo", "tipo": "cobro", "monto": D("100"), "descripcion": "x"}
        base.update(datos)
        return MovimientoCaja(**base)

    def test_un_monto_cero_no_es_valido(self):
        with self.assertRaises(ValidationError):
            self.nuevo(monto=D("0")).full_clean()

    def test_lo_que_siempre_entra_no_acepta_un_monto_negativo(self):
        for tipo, caja in (("saldo_inicial", "efectivo"), ("cobro", "efectivo"), ("sena", "senas_efectivo")):
            with self.subTest(tipo=tipo), self.assertRaises(ValidationError):
                self.nuevo(tipo=tipo, caja=caja, monto=D("-1")).full_clean()

    def test_lo_que_siempre_sale_no_acepta_un_monto_positivo(self):
        for tipo in ("retiro", "gasto", "compra_mercaderia", "devolucion"):
            with self.subTest(tipo=tipo), self.assertRaises(ValidationError):
                self.nuevo(tipo=tipo, monto=D("1")).full_clean()

    def test_los_pases_y_los_ajustes_aceptan_los_dos_signos(self):
        for tipo in ("pase", "ajuste", "pase_sena"):
            for monto in (D("50"), D("-50")):
                with self.subTest(tipo=tipo, monto=monto):
                    self.nuevo(tipo=tipo, monto=monto).full_clean()        # no da error

    def test_el_saldo_inicial_no_va_en_las_cajas_de_senas(self):
        with self.assertRaises(ValidationError):
            self.nuevo(tipo="saldo_inicial", caja="senas_efectivo").full_clean()

    def test_una_sena_solo_va_en_las_cajas_de_senas(self):
        with self.assertRaises(ValidationError):
            self.nuevo(tipo="sena", caja="efectivo").full_clean()

    def test_un_retiro_no_sale_de_las_senas(self):
        with self.assertRaises(ValidationError):
            self.nuevo(tipo="retiro", caja="senas_efectivo", monto=D("-10")).full_clean()

    def test_un_anulado_tiene_que_tener_la_fecha_de_anulacion(self):
        with self.assertRaises(ValidationError):
            self.nuevo(anulado=True).full_clean()

    def test_un_movimiento_no_se_borra(self):
        guardado = movimiento()

        with self.assertRaises(ValidationError):
            guardado.delete()

        self.assertTrue(MovimientoCaja.objects.filter(pk=guardado.pk).exists())


# ---------- Ninguna caja queda en negativo ----------

class NuncaEnNegativoTests(TestCase):
    def setUp(self):
        movimiento(monto="1000")

    def test_una_salida_mayor_a_lo_que_hay_no_se_guarda(self):
        with self.assertRaises(ReglaDeNegocioError) as error:
            servicios.registrar_movimiento("efectivo", "retiro", D("-1500"), "Retiro")

        self.assertIn("hay $ 1.000", str(error.exception))
        self.assertEqual(servicios.saldo_de("efectivo"), D("1000"))
        self.assertEqual(MovimientoCaja.objects.count(), 1)

    def test_una_salida_igual_a_lo_que_hay_deja_la_caja_en_cero(self):
        servicios.registrar_movimiento("efectivo", "retiro", D("-1000"), "Retiro")

        self.assertEqual(servicios.saldo_de("efectivo"), D("0"))

    def test_un_centavo_mas_de_lo_que_hay_ya_no_se_puede(self):
        with self.assertRaises(ReglaDeNegocioError):
            servicios.registrar_movimiento("efectivo", "retiro", D("-1000.01"), "Retiro")

    def test_lo_que_hay_en_otra_caja_no_cuenta(self):
        movimiento(caja="digital", monto="5000")

        with self.assertRaises(ReglaDeNegocioError):
            servicios.registrar_movimiento("efectivo", "retiro", D("-2000"), "Retiro")

    def test_una_entrada_se_guarda_aunque_la_caja_este_en_cero(self):
        servicios.registrar_movimiento("digital", "cobro", D("10"), "Cobro")

        self.assertEqual(servicios.saldo_de("digital"), D("10"))


# ---------- Saldo inicial ----------

class SaldoInicialTests(TestCase):
    def test_carga_el_saldo_y_lo_anota_en_el_historial(self):
        mov = servicios.cargar_saldo_inicial("efectivo", D("150000"), "Contado el lunes")

        self.assertEqual(servicios.saldo_de("efectivo"), D("150000"))
        self.assertEqual((mov.tipo, mov.descripcion, mov.nota), ("saldo_inicial", "Saldo inicial de Efectivo", "Contado el lunes"))
        cambio = Cambio.objects.get()
        self.assertEqual((cambio.area, cambio.accion, cambio.movimiento_caja), ("dinero", "alta", mov))
        self.assertEqual(cambio.frase, "Cargaste el saldo inicial de Efectivo: $ 150.000.")

    def test_se_carga_una_sola_vez_por_caja(self):
        servicios.cargar_saldo_inicial("efectivo", D("1000"))

        with self.assertRaises(ReglaDeNegocioError):
            servicios.cargar_saldo_inicial("efectivo", D("2000"))

        self.assertEqual(servicios.saldo_de("efectivo"), D("1000"))

    def test_cada_caja_principal_tiene_el_suyo(self):
        servicios.cargar_saldo_inicial("efectivo", D("1000"))
        servicios.cargar_saldo_inicial("digital", D("2000"))

        self.assertEqual(servicios.saldos()["digital"], D("2000"))

    def test_despues_de_anularlo_se_puede_cargar_de_nuevo(self):
        primero = servicios.cargar_saldo_inicial("efectivo", D("1000"))
        servicios.anular_movimiento(primero, "Me equivoqué de caja")

        servicios.cargar_saldo_inicial("efectivo", D("3000"))

        self.assertEqual(servicios.saldo_de("efectivo"), D("3000"))

    def test_no_se_carga_en_las_cajas_de_senas(self):
        for caja in ("senas_efectivo", "senas_digital"):
            with self.subTest(caja=caja), self.assertRaises(ReglaDeNegocioError):
                servicios.cargar_saldo_inicial(caja, D("100"))

    def test_un_monto_cero_negativo_o_vacio_no_se_acepta(self):
        for monto in (D("0"), D("-5"), None):
            with self.subTest(monto=monto), self.assertRaises(ReglaDeNegocioError):
                servicios.cargar_saldo_inicial("efectivo", monto)
        self.assertFalse(MovimientoCaja.objects.exists())

    def test_si_falla_el_historial_no_queda_ni_el_movimiento(self):
        # Todo o nada: el movimiento y su renglón del historial se guardan juntos
        with mock.patch("negocio.servicios.caja.anotar", side_effect=RuntimeError("falla simulada")):
            with self.assertRaises(RuntimeError):
                servicios.cargar_saldo_inicial("efectivo", D("1000"))

        self.assertFalse(MovimientoCaja.objects.exists())
        self.assertFalse(Cambio.objects.exists())


# ---------- Corregir ----------

class CorregirTests(TestCase):
    def setUp(self):
        self.inicial = servicios.cargar_saldo_inicial("efectivo", D("1000"))

    def test_corrige_el_monto_y_guarda_el_anterior_en_el_historial(self):
        servicios.corregir_movimiento(self.inicial, D("1200"))

        self.inicial.refresh_from_db()
        self.assertEqual(self.inicial.monto, D("1200"))
        cambio = Cambio.objects.filter(accion="correccion").get()
        self.assertEqual((cambio.antes, cambio.despues), ("$ 1.000", "$ 1.200"))
        self.assertEqual(cambio.frase, "Corregiste «Saldo inicial de Efectivo» (Efectivo): de $ 1.000 a $ 1.200.")

    def test_el_saldo_refleja_la_correccion(self):
        servicios.corregir_movimiento(self.inicial, D("400"))

        self.assertEqual(servicios.saldo_de("efectivo"), D("400"))

    def test_el_monto_se_escribe_en_positivo_y_el_tipo_pone_el_signo(self):
        retiro = servicios.registrar_movimiento("efectivo", "retiro", D("-200"), "Retiro del dueño")

        servicios.corregir_movimiento(retiro, D("300"))

        retiro.refresh_from_db()
        self.assertEqual(retiro.monto, D("-300"))
        self.assertEqual(servicios.saldo_de("efectivo"), D("700"))

    def test_cambiar_solo_la_nota_no_toca_el_monto_y_queda_anotado(self):
        servicios.corregir_movimiento(self.inicial, D("1000"), "Contado de nuevo")

        self.inicial.refresh_from_db()
        self.assertEqual((self.inicial.monto, self.inicial.nota), (D("1000"), "Contado de nuevo"))
        cambio = Cambio.objects.filter(accion="correccion").get()
        self.assertEqual(cambio.frase, "Cambiaste la nota de «Saldo inicial de Efectivo» (Efectivo).")
        self.assertEqual((cambio.antes, cambio.despues), ("", "Contado de nuevo"))

    def test_corregir_sin_cambiar_nada_da_error(self):
        with self.assertRaises(ReglaDeNegocioError):
            servicios.corregir_movimiento(self.inicial, D("1000"))

        self.assertFalse(Cambio.objects.filter(accion="correccion").exists())

    def test_un_monto_cero_o_vacio_no_se_acepta(self):
        for monto in (D("0"), None, D("-10")):
            with self.subTest(monto=monto), self.assertRaises(ReglaDeNegocioError):
                servicios.corregir_movimiento(self.inicial, monto)

    def test_un_anulado_no_se_corrige(self):
        servicios.anular_movimiento(self.inicial)

        with self.assertRaises(ReglaDeNegocioError):
            servicios.corregir_movimiento(self.inicial, D("5000"))

    def test_lo_que_viene_de_una_venta_no_se_corrige_desde_la_caja(self):
        cobro = movimiento(tipo="cobro", monto="300", descripcion="Venta #4")

        with self.assertRaises(ReglaDeNegocioError) as error:
            servicios.corregir_movimiento(cobro, D("400"))

        self.assertIn("desde donde se cargó", str(error.exception))

    def test_una_correccion_que_deja_la_caja_en_negativo_no_se_guarda(self):
        servicios.registrar_movimiento("efectivo", "retiro", D("-800"), "Retiro")

        with self.assertRaises(ReglaDeNegocioError):
            servicios.corregir_movimiento(self.inicial, D("500"))       # 500 − 800 = −300

        self.inicial.refresh_from_db()
        self.assertEqual(self.inicial.monto, D("1000"))
        self.assertFalse(Cambio.objects.filter(accion="correccion").exists())

    def test_usa_los_datos_guardados_y_no_los_del_objeto_en_memoria(self):
        en_memoria = MovimientoCaja.objects.get(pk=self.inicial.pk)
        en_memoria.monto = D("999999")         # un cambio que nunca se guardó

        servicios.corregir_movimiento(en_memoria, D("1100"))

        self.assertEqual(Cambio.objects.filter(accion="correccion").get().antes, "$ 1.000")


# ---------- Anular ----------

class AnularTests(TestCase):
    def setUp(self):
        self.inicial = servicios.cargar_saldo_inicial("efectivo", D("1000"))

    def test_anular_marca_fecha_y_motivo_y_lo_anota(self):
        servicios.anular_movimiento(self.inicial, "Lo cargué dos veces")

        self.inicial.refresh_from_db()
        self.assertTrue(self.inicial.anulado)
        self.assertIsNotNone(self.inicial.anulado_fecha)
        self.assertEqual(self.inicial.anulado_motivo, "Lo cargué dos veces")
        cambio = Cambio.objects.filter(accion="anulacion").get()
        self.assertEqual(cambio.frase, "Anulaste «Saldo inicial de Efectivo» (Efectivo, $ 1.000). Motivo: Lo cargué dos veces")

    def test_anular_no_borra_el_movimiento_y_deja_de_sumar(self):
        servicios.anular_movimiento(self.inicial)

        self.assertTrue(MovimientoCaja.objects.filter(pk=self.inicial.pk).exists())
        self.assertEqual(servicios.saldo_de("efectivo"), D("0"))

    def test_anular_dos_veces_da_error(self):
        servicios.anular_movimiento(self.inicial)

        with self.assertRaises(ReglaDeNegocioError):
            servicios.anular_movimiento(self.inicial)

    def test_no_se_anula_si_la_caja_queda_en_negativo(self):
        servicios.registrar_movimiento("efectivo", "retiro", D("-600"), "Retiro")

        with self.assertRaises(ReglaDeNegocioError):
            servicios.anular_movimiento(self.inicial)

        self.inicial.refresh_from_db()
        self.assertFalse(self.inicial.anulado)

    def test_anular_una_salida_devuelve_la_plata_a_la_caja(self):
        retiro = servicios.registrar_movimiento("efectivo", "retiro", D("-600"), "Retiro")

        servicios.anular_movimiento(retiro)

        self.assertEqual(servicios.saldo_de("efectivo"), D("1000"))

    def test_lo_que_viene_de_una_venta_no_se_anula_desde_la_caja(self):
        cobro = movimiento(tipo="cobro", monto="300")

        with self.assertRaises(ReglaDeNegocioError):
            servicios.anular_movimiento(cobro)

    def test_un_motivo_muy_largo_se_guarda_entero_y_la_frase_se_recorta(self):
        motivo = "m" * 290

        servicios.anular_movimiento(self.inicial, motivo)

        self.inicial.refresh_from_db()
        self.assertEqual(self.inicial.anulado_motivo, motivo)
        frase = Cambio.objects.filter(accion="anulacion").get().frase
        self.assertEqual(len(frase), 300)
        self.assertTrue(frase.endswith("…"))


# ---------- Historial ----------

class HistorialTests(TestCase):
    def test_un_renglon_del_historial_no_se_modifica(self):
        cambio = servicios.anotar("dinero", "alta", "Algo")
        cambio.frase = "Otra cosa"

        with self.assertRaises(ValidationError):
            cambio.save()

        self.assertEqual(Cambio.objects.get().frase, "Algo")

    def test_un_renglon_del_historial_no_se_borra(self):
        cambio = servicios.anotar("dinero", "alta", "Algo")

        with self.assertRaises(ValidationError):
            cambio.delete()

        self.assertEqual(Cambio.objects.count(), 1)

    def test_cada_operacion_deja_su_renglon(self):
        inicial = servicios.cargar_saldo_inicial("digital", D("5000"))
        servicios.corregir_movimiento(inicial, D("5500"), "Mirado en la app")     # monto y nota: dos renglones
        servicios.anular_movimiento(inicial)

        acciones = list(Cambio.objects.order_by("id").values_list("accion", flat=True))
        self.assertEqual(acciones, ["alta", "correccion", "correccion", "anulacion"])
        self.assertTrue(all(c.movimiento_caja_id == inicial.pk for c in Cambio.objects.all()))


# ---------- Cómo se muestran en el admin ----------

class TextosTests(TestCase):
    def test_el_texto_de_un_movimiento_dice_caja_detalle_monto_y_si_esta_anulado(self):
        mov = servicios.cargar_saldo_inicial("efectivo", D("1000"))
        self.assertEqual(str(mov), f"Movimiento #{mov.pk} | Efectivo | Saldo inicial de Efectivo | entra $ 1.000")
        retiro = servicios.registrar_movimiento("efectivo", "retiro", D("-250"), "Retiro")
        self.assertTrue(str(retiro).endswith("| sale $ 250"))
        self.assertEqual(retiro.monto_absoluto, D("250"))

        servicios.anular_movimiento(retiro)
        retiro.refresh_from_db()
        self.assertTrue(str(retiro).endswith("| sale $ 250 (anulado)"))

    def test_el_texto_de_un_cambio_tiene_fecha_y_frase(self):
        cambio = servicios.anotar("dinero", "alta", "Algo")

        self.assertTrue(str(cambio).endswith("| Algo"))


# ---------- Formato de los montos ----------

class FormatoTests(TestCase):
    def test_pesos_en_formato_argentino(self):
        casos = {D("42500"): "$ 42.500", D("1234.5"): "$ 1.234,50", D("0.01"): "$ 0,01", D("-3000"): "$ 3.000"}
        for valor, esperado in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(pesos(valor), esperado)
