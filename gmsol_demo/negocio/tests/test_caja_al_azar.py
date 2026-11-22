"""Pruebas con datos al azar de la caja (hypothesis).

En lugar de unos pocos casos escritos a mano, hypothesis genera cientos de secuencias de operaciones
(saldo inicial, cobros, retiros, correcciones, anulaciones) con montos al azar. Un "modelo" en Python
puro lleva la cuenta por su lado, y después de CADA operación se comprueba que:

  1. el saldo de cada caja es igual a la cuenta del modelo (la suma de lo no anulado);
  2. ninguna caja queda en negativo;
  3. si el modelo dice que una operación tenía que fallar, falló y no cambió nada;
  4. cada operación que se guardó dejó su renglón en el historial.

Si encuentra una secuencia que rompe algo, hypothesis la achica hasta el caso más chico y la muestra.

Correr solo este archivo:
    python manage.py test negocio.tests.test_caja_al_azar
"""
from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase

from negocio import servicios
from negocio.models import Cambio, MovimientoCaja
from negocio.servicios import ReglaDeNegocioError

CAJAS = ("efectivo", "digital")
montos = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("500000"), places=2,
                     allow_nan=False, allow_infinity=False)

# Una operación: (qué, caja, monto, a qué movimiento anterior apunta)
operacion = st.tuples(
    st.sampled_from(["saldo_inicial", "cobro", "retiro", "corregir", "anular"]),
    st.sampled_from(CAJAS),
    montos,
    st.integers(min_value=0, max_value=50),
)


class CajaAlAzarTests(TestCase):

    @settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(st.lists(operacion, min_size=1, max_size=25))
    def test_el_saldo_siempre_es_la_suma_y_nunca_queda_en_negativo(self, operaciones):
        modelo = []        # [{"pk", "caja", "tipo", "monto", "anulado"}], la cuenta "a mano"

        def saldo_modelo(caja):
            return sum((m["monto"] for m in modelo if m["caja"] == caja and not m["anulado"]), Decimal("0"))

        for que, caja, monto, indice in operaciones:
            renglones_antes = Cambio.objects.count()
            manuales = [m for m in modelo if m["tipo"] in ("saldo_inicial", "retiro") and not m["anulado"]]
            objetivo = manuales[indice % len(manuales)] if manuales else None

            # Qué tendría que pasar, según el modelo
            if que == "saldo_inicial":
                debe_fallar = any(m["caja"] == caja and m["tipo"] == "saldo_inicial" and not m["anulado"] for m in modelo)
            elif que == "cobro":
                debe_fallar = False
            elif que == "retiro":
                debe_fallar = saldo_modelo(caja) - monto < 0
            elif objetivo is None:
                continue                       # nada para corregir o anular todavía
            elif que == "corregir":
                nuevo = monto if objetivo["tipo"] == "saldo_inicial" else -monto
                debe_fallar = (nuevo == objetivo["monto"] or
                               saldo_modelo(objetivo["caja"]) - objetivo["monto"] + nuevo < 0)
            else:   # anular
                debe_fallar = saldo_modelo(objetivo["caja"]) - objetivo["monto"] < 0

            # Lo que pasa de verdad
            try:
                if que == "saldo_inicial":
                    mov = servicios.cargar_saldo_inicial(caja, monto)
                    modelo.append({"pk": mov.pk, "caja": caja, "tipo": "saldo_inicial", "monto": monto, "anulado": False})
                elif que == "cobro":
                    mov = servicios.registrar_movimiento(caja, "cobro", monto, "Cobro al azar")
                    modelo.append({"pk": mov.pk, "caja": caja, "tipo": "cobro", "monto": monto, "anulado": False})
                elif que == "retiro":
                    mov = servicios.registrar_movimiento(caja, "retiro", -monto, "Retiro al azar")
                    modelo.append({"pk": mov.pk, "caja": caja, "tipo": "retiro", "monto": -monto, "anulado": False})
                elif que == "corregir":
                    servicios.corregir_movimiento(MovimientoCaja.objects.get(pk=objetivo["pk"]), monto)
                    objetivo["monto"] = nuevo
                else:
                    servicios.anular_movimiento(MovimientoCaja.objects.get(pk=objetivo["pk"]))
                    objetivo["anulado"] = True
                fallo = False
            except ReglaDeNegocioError:
                fallo = True

            # Comprobaciones después de cada operación
            self.assertEqual(fallo, debe_fallar, f"{que} {caja} {monto}: el sistema y el modelo no coinciden")
            for c in CAJAS:
                self.assertEqual(servicios.saldo_de(c), saldo_modelo(c), f"saldo de {c} después de {que}")
                self.assertGreaterEqual(servicios.saldo_de(c), 0, f"{c} quedó en negativo")
            renglones_nuevos = Cambio.objects.count() - renglones_antes
            if fallo:
                self.assertEqual(renglones_nuevos, 0, "una operación que falló dejó historial")
            elif que in ("saldo_inicial", "corregir", "anular"):
                self.assertEqual(renglones_nuevos, 1, f"{que} tiene que dejar un renglón en el historial")
