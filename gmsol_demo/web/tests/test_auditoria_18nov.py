"""Arreglos de la auditoría del 18/11/2026: ids inválidos, montos negativos, búsqueda por número."""
from django.urls import reverse

from catalogo.models import Cliente, OrdenTrabajo, Telefono, Venta
from web.tests import test_pantallas
from web.tests.test_pantallas import Base   # sin tests propios: importarla no los repite


class IdsInvalidosTests(Base):
    """Un id con letras en un formulario ya no da error 500: da 404 y no cambia nada."""

    def test_accion_de_la_orden_con_id_invalido(self):
        o = self.orden(pagado="500")
        for accion, campo in (("quitar_pago", "pago"), ("estado", "equipo"), ("quitar_reparacion", "linea"),
                              ("quitar_producto", "linea"), ("anular_devolucion", "devolucion")):
            with self.subTest(accion=accion):
                r = self.client.post(reverse("web:orden_detalle", args=[o.id]), {"accion": accion, campo: "abc"})
                self.assertEqual(r.status_code, 404)
        self.assertEqual(o.pagos.count(), 1)

    def test_devoluciones_con_id_invalido(self):
        r = self.client.post(reverse("web:devoluciones"), {"accion": "devolver_reparacion", "linea": "abc"})
        self.assertEqual(r.status_code, 302)       # avisa "Elegí qué reparación se devuelve."
        r = self.client.post(reverse("web:devoluciones"), {"accion": "anular", "devolucion": "1x"})
        self.assertEqual(r.status_code, 404)

    def test_telefono_con_id_invalido(self):
        r = self.client.post(reverse("web:cliente_detalle", args=[self.juan.id]),
                             {"accion": "quitar_telefono", "telefono": "abc"})
        self.assertEqual(r.status_code, 404)


class MontoNegativoTests(Base):
    datos = test_pantallas.VentaRapidaTests.datos      # mismos datos de la venta rápida, sin repetir sus tests

    def test_monto_negativo_marca_el_campo(self):
        r = self.client.post(reverse("web:venta_rapida"), self.datos(**{"pago-0-monto": "-500"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "con-error")
        self.assertFalse(Venta.objects.exists())


class BuscarPorNumeroTests(Base):
    def test_numero_sin_coincidencias_de_cliente_abre_la_orden(self):
        o = self.orden()
        r = self.client.get(reverse("web:ordenes") + f"?estado=todas&q={o.id}")
        self.assertRedirects(r, reverse("web:orden_detalle", args=[o.id]))

    def test_numero_que_tambien_es_un_telefono_muestra_la_lista(self):
        o = self.orden()
        ana = Cliente.objects.create(nombre="Ana Torres")
        Telefono.objects.create(cliente=ana, numero=f"351-555 {o.id:04d}", principal=True)
        de_ana = OrdenTrabajo.objects.create(cliente=ana)
        r = self.client.get(reverse("web:ordenes") + f"?estado=todas&q={o.id:04d}")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f"#{o.id}<")           # la orden con ese número, primera
        self.assertContains(r, f"#{de_ana.id}<")      # y la del cliente con ese teléfono
        html = r.content.decode()
        self.assertLess(html.index(f"#{o.id}<"), html.index(f"#{de_ana.id}<"))
        # Con "#" se abre directo, aunque coincida un teléfono
        r = self.client.get(reverse("web:ordenes") + f"?q=%23{o.id}")
        self.assertRedirects(r, reverse("web:orden_detalle", args=[o.id]))

    def test_telefono_con_guiones_se_encuentra_escribiendo_solo_numeros(self):
        Telefono.objects.create(cliente=self.juan, numero="358-412 3456", principal=True)
        o = self.orden()
        r = self.client.get(reverse("web:ordenes") + "?estado=todas&q=4123456")
        self.assertContains(r, f"#{o.id}<")
