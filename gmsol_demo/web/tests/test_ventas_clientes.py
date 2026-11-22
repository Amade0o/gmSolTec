"""Pantallas de Ventas y Clientes."""
from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from negocio.models import Cliente, LineaProductoVenta, Pago, Telefono, Venta
from negocio.servicios import cerrar_orden, vender_directo
from web.tests.test_pantallas import Base, textos

D = Decimal


class LoginTests(Base):
    def test_piden_login(self):
        self.client.logout()
        for url in (reverse("web:ventas"), reverse("web:clientes"), reverse("web:cliente_nuevo"),
                    reverse("web:cliente_detalle", args=[self.juan.id])):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)


class VentasTests(Base):
    def venta_directa(self, cliente=None, cantidad=2):
        return vender_directo(
            [LineaProductoVenta(producto=self.cable, cantidad_adquirida=cantidad)],
            [Pago(metodo_pago=self.efectivo, monto=D("2500") * cantidad)], cliente=cliente)

    def test_lista_y_total_del_periodo(self):
        directa = self.venta_directa()
        de_orden = cerrar_orden(self.orden("1000", estado="arreglado", pagado="1000"))
        r = self.client.get(reverse("web:ventas"))
        self.assertContains(r, f"#{directa.id}<")
        self.assertContains(r, f"#{de_orden.id}<")
        self.assertContains(r, "2× Cable USB-C")
        self.assertContains(r, f"Orden #{de_orden.orden_trabajo_id}")
        self.assertContains(r, "$ 6.000")         # 5000 + 1000

    def test_filtro_por_periodo(self):
        vieja = self.venta_directa()
        Venta.objects.filter(pk=vieja.id).update(fecha=timezone.now() - timedelta(days=40))
        nueva = self.venta_directa(cantidad=1)
        r = self.client.get(reverse("web:ventas") + "?periodo=hoy")
        self.assertContains(r, f"#{nueva.id}<")
        self.assertNotContains(r, f"#{vieja.id}<")
        r = self.client.get(reverse("web:ventas") + "?periodo=todas")
        self.assertContains(r, f"#{vieja.id}<")

    def test_buscar_por_cliente_y_por_numero(self):
        de_juan = self.venta_directa(cliente=self.juan)
        sin_cliente = self.venta_directa(cantidad=1)
        r = self.client.get(reverse("web:ventas") + "?periodo=todas&q=pérez")
        self.assertContains(r, f"#{de_juan.id}<")
        self.assertNotContains(r, f"#{sin_cliente.id}<")
        r = self.client.get(reverse("web:ventas") + f"?q=%23{sin_cliente.id}")
        self.assertRedirects(r, reverse("web:venta_detalle", args=[sin_cliente.id]))

    def test_detalle_venta_directa(self):
        venta = self.venta_directa(cliente=self.juan)
        r = self.client.get(reverse("web:venta_detalle", args=[venta.id]))
        self.assertContains(r, "Venta directa")
        self.assertContains(r, "Cable USB-C")
        self.assertContains(r, "Efectivo")

    def test_detalle_venta_de_orden_muestra_la_orden(self):
        orden = self.orden("1000", estado="arreglado", pagado="1000")
        venta = cerrar_orden(orden)
        r = self.client.get(reverse("web:venta_detalle", args=[venta.id]))
        self.assertContains(r, f"orden #{orden.id}")
        self.assertContains(r, "Módulo OLED")
        self.assertContains(r, "Efectivo")         # el pago es de la orden

    def test_la_orden_cerrada_enlaza_a_su_venta(self):
        venta = cerrar_orden(self.orden("1000", estado="arreglado", pagado="1000"))
        r = self.client.get(reverse("web:orden_detalle", args=[venta.orden_trabajo_id]))
        self.assertContains(r, reverse("web:venta_detalle", args=[venta.id]))


class ClientesTests(Base):
    def test_lista_y_busqueda(self):
        Telefono.objects.create(cliente=self.juan, numero="3584111111", principal=True)
        ana = Cliente.objects.create(nombre="Ana Torres")
        self.orden()
        r = self.client.get(reverse("web:clientes"))
        self.assertContains(r, "Juan Pérez")
        self.assertContains(r, "3584111111")
        self.assertContains(r, "Ana Torres")
        r = self.client.get(reverse("web:clientes") + "?q=4111")
        self.assertContains(r, "Juan Pérez")
        self.assertNotContains(r, ana.nombre)

    def test_crear_cliente(self):
        r = self.client.post(reverse("web:cliente_nuevo"), {"nombre": "Lucía Fernández", "telefono": "3584555555",
                                                             "email": "", "direccion": "", "notas": ""})
        lucia = Cliente.objects.get(nombre="Lucía Fernández")
        self.assertRedirects(r, reverse("web:cliente_detalle", args=[lucia.id]))
        self.assertTrue(lucia.telefonos.get().principal)

    def test_crear_y_seguir_a_nueva_orden(self):
        r = self.client.post(reverse("web:cliente_nuevo"), {"nombre": "Lucía", "telefono": "", "despues": "orden"})
        lucia = Cliente.objects.get(nombre="Lucía")
        self.assertRedirects(r, reverse("web:orden_nueva") + f"?cliente={lucia.id}")
        r = self.client.get(r.url)
        self.assertContains(r, f'<option value="{lucia.id}" selected>')

    def test_sin_nombre_no_guarda(self):
        r = self.client.post(reverse("web:cliente_nuevo"), {"nombre": "", "telefono": "123"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Cliente.objects.count(), 1)

    def test_ficha_con_ordenes_y_saldo(self):
        o = self.orden("1000", pagado="400")
        r = self.client.get(reverse("web:cliente_detalle", args=[self.juan.id]))
        self.assertContains(r, f"#{o.id}<")
        self.assertContains(r, "Debe $ 600")

    def test_editar_datos(self):
        r = self.client.post(reverse("web:cliente_detalle", args=[self.juan.id]), {
            "accion": "datos", "cli-nombre": "Juan Carlos Pérez", "cli-email": "juan@ejemplo.com",
            "cli-direccion": "", "cli-notas": ""})
        self.assertRedirects(r, reverse("web:cliente_detalle", args=[self.juan.id]))
        self.juan.refresh_from_db()
        self.assertEqual(self.juan.nombre, "Juan Carlos Pérez")

    def test_telefonos(self):
        url = reverse("web:cliente_detalle", args=[self.juan.id])
        self.client.post(url, {"accion": "telefono", "tel-numero": "111"})
        self.client.post(url, {"accion": "telefono", "tel-numero": "222", "tel-principal": "on"})
        self.assertEqual(self.juan.telefonos.get(principal=True).numero, "222")
        r = self.client.post(url, {"accion": "telefono", "tel-numero": "222"})
        self.assertIn("Ese teléfono ya está cargado.", textos(r))
        uno = self.juan.telefonos.get(numero="111")
        self.client.post(url, {"accion": "principal", "telefono": uno.id})
        self.assertEqual(self.juan.telefonos.get(principal=True).numero, "111")
        self.client.post(url, {"accion": "quitar_telefono", "telefono": uno.id})
        self.assertEqual(self.juan.telefonos.get().numero, "222")
        self.assertTrue(self.juan.telefonos.get().principal)

    def test_no_toca_telefonos_de_otro_cliente(self):
        ajeno = Telefono.objects.create(cliente=Cliente.objects.create(nombre="Ana"), numero="999")
        r = self.client.post(reverse("web:cliente_detalle", args=[self.juan.id]),
                             {"accion": "quitar_telefono", "telefono": ajeno.id})
        self.assertEqual(r.status_code, 404)
        self.assertTrue(Telefono.objects.filter(pk=ajeno.id).exists())
