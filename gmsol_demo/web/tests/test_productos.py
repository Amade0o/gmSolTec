"""Pantallas de Productos."""
from decimal import Decimal

from django.urls import reverse

from negocio.models import CategoriaProducto, LineaProductoVenta, Pago, Producto
from negocio.servicios import vender_directo
from web.tests.test_pantallas import Base

D = Decimal


class ProductosTests(Base):
    def datos(self, **cambios):
        datos = {"nombre": "Cargador 20W", "categoria": self.cable.categoria_id, "marca": "",
                 "precio_compra": "4000", "precio_venta": "6000"}
        datos.update(cambios)
        return datos

    def test_piden_login(self):
        self.client.logout()
        for url in (reverse("web:productos"), reverse("web:producto_nuevo"),
                    reverse("web:producto_detalle", args=[self.cable.id])):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_lista_filtros(self):
        viejo = Producto.objects.create(nombre="Cable micro USB", categoria=self.cable.categoria,
                                        precio_compra=D("500"), precio_venta=D("900"), activo=False)
        r = self.client.get(reverse("web:productos"))
        self.assertContains(r, "Cable USB-C")
        self.assertContains(r, "150 %")                 # (2500 - 1000) / 1000
        self.assertNotContains(r, viejo.nombre)
        r = self.client.get(reverse("web:productos") + "?estado=inactivos")
        self.assertContains(r, viejo.nombre)
        self.assertNotContains(r, "Cable USB-C<")
        otra = CategoriaProducto.objects.create(nombre="Fundas")
        r = self.client.get(reverse("web:productos") + f"?categoria={otra.id}")
        self.assertNotContains(r, "Cable USB-C<")
        r = self.client.get(reverse("web:productos") + "?q=usb-c")
        self.assertContains(r, "Cable USB-C")

    def test_crear(self):
        r = self.client.post(reverse("web:producto_nuevo"), self.datos())
        nuevo = Producto.objects.get(nombre="Cargador 20W")
        self.assertRedirects(r, reverse("web:producto_detalle", args=[nuevo.id]))
        self.assertEqual(nuevo.precio_venta, D("6000"))

    def test_guardar_y_cargar_otro(self):
        r = self.client.post(reverse("web:producto_nuevo"), self.datos(despues="otro"))
        self.assertRedirects(r, reverse("web:producto_nuevo"))

    def test_nombre_repetido_no_guarda(self):
        r = self.client.post(reverse("web:producto_nuevo"), self.datos(nombre="Cable USB-C"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Producto.objects.filter(nombre="Cable USB-C").count(), 1)

    def test_editar_precio_con_categoria_desactivada(self):
        CategoriaProducto.objects.filter(pk=self.cable.categoria_id).update(activa=False)
        url = reverse("web:producto_detalle", args=[self.cable.id])
        r = self.client.post(url, self.datos(nombre="Cable USB-C", precio_venta="3000"))
        self.assertRedirects(r, url)
        self.cable.refresh_from_db()
        self.assertEqual(self.cable.precio_venta, D("3000"))

    def test_no_se_puede_elegir_una_categoria_desactivada(self):
        apagada = CategoriaProducto.objects.create(nombre="Viejas", activa=False)
        r = self.client.post(reverse("web:producto_nuevo"), self.datos(categoria=apagada.id))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Producto.objects.filter(nombre="Cargador 20W").exists())

    def test_desactivar_y_activar(self):
        url = reverse("web:producto_detalle", args=[self.cable.id])
        self.client.post(url, {"accion": "desactivar"})
        self.cable.refresh_from_db()
        self.assertFalse(self.cable.activo)
        self.client.post(url, {"accion": "activar"})
        self.cable.refresh_from_db()
        self.assertTrue(self.cable.activo)

    def test_ultimas_ventas(self):
        venta = vender_directo([LineaProductoVenta(producto=self.cable, cantidad_adquirida=1)],
                               [Pago(metodo_pago=self.efectivo, monto=D("2500"))])
        r = self.client.get(reverse("web:producto_detalle", args=[self.cable.id]))
        self.assertContains(r, f"Venta #{venta.id}")

    def test_margen_en_vivo(self):
        r = self.client.post(reverse("web:producto_margen"), {"precio_compra": "1000", "precio_venta": "800"})
        self.assertContains(r, "-20 %")
        self.assertContains(r, "Se vende por debajo del costo")
        r = self.client.post(reverse("web:producto_margen"), {"precio_compra": "", "precio_venta": "800"})
        self.assertContains(r, "Cargá los dos precios")
