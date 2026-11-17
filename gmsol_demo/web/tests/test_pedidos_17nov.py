"""Pedidos del dueño del 17/11/2026: alta rápida del catálogo, eliminar, devolver una reparación,
filas de producto sin "1" por defecto y "Sin precio todavía"."""
import json
from decimal import Decimal

from django.urls import reverse

from catalogo.models import (
    CategoriaReparacion, Devolucion, LineaReparacion, Marca, ModeloEquipo, Producto, Reparacion, Venta,
)
from web.tests.test_pantallas import Base

D = Decimal


class AltaRapidaTests(Base):
    """"+ Nuevo" al lado de los desplegables: se carga sin salir de la pantalla."""

    def url(self, seccion):
        return reverse("web:alta_rapida", args=[seccion])

    def test_los_desplegables_tienen_el_boton(self):
        r = self.client.get(reverse("web:orden_nueva"))
        self.assertContains(r, "+ Nuevo modelo")
        self.assertContains(r, "+ Nueva reparación (al catálogo)")
        r = self.client.get(reverse("web:producto_nuevo"))
        self.assertContains(r, "+ Nueva categoría")
        self.assertContains(r, "+ Nueva marca")

    def test_modelo_con_marca_nueva(self):
        r = self.client.post(self.url("modelos"), {
            "destino": "id_eq-modelo", "rapido-marca": "", "rapido-nuevo_padre": "Motorola",
            "rapido-nombre": "Moto G54", "rapido-tipo": "celular"})
        self.assertEqual(r.status_code, 200)
        modelo = ModeloEquipo.objects.get(nombre="Moto G54")
        self.assertEqual(modelo.marca.nombre, "Motorola")
        evento = json.loads(r["HX-Trigger"])["catalogo-agregado"]
        self.assertEqual(evento, {"seccion": "modelos", "id": modelo.pk, "texto": "Motorola Moto G54",
                                  "destino": "id_eq-modelo"})

    def test_marca_que_ya_existe_no_se_duplica(self):
        self.client.post(self.url("modelos"), {"rapido-nuevo_padre": "samsung", "rapido-nombre": "A54",
                                               "rapido-tipo": "celular"})
        self.assertEqual(Marca.objects.filter(nombre__iexact="samsung").count(), 1)

    def test_si_falla_no_queda_la_marca_nueva(self):
        r = self.client.post(self.url("modelos"), {"rapido-nuevo_padre": "Nokia", "rapido-nombre": "",
                                                   "rapido-tipo": "celular"})
        self.assertNotIn("HX-Trigger", r)
        self.assertContains(r, "Nuevo modelo de equipo")             # vuelve el formulario con el error
        self.assertFalse(Marca.objects.filter(nombre="Nokia").exists())

    def test_reparacion_nueva(self):
        r = self.client.post(self.url("reparaciones"), {
            "destino": "formset-rep", "rapido-categoria": self.reparacion.categoria_id,
            "rapido-nombre": "Cambio de módulo especial"})
        self.assertTrue(Reparacion.objects.filter(nombre="Cambio de módulo especial").exists())
        self.assertEqual(json.loads(r["HX-Trigger"])["catalogo-agregado"]["destino"], "formset-rep")

    def test_si_ya_existe_lo_elige(self):
        r = self.client.post(self.url("modelos"), {"destino": "id_eq-modelo", "rapido-nuevo_padre": "SAMSUNG",
                                                   "rapido-nombre": "galaxy a14", "rapido-tipo": "celular"})
        self.assertEqual(json.loads(r["HX-Trigger"])["catalogo-agregado"]["id"], self.modelo.pk)
        self.assertEqual(ModeloEquipo.objects.count(), 1)
        self.modelo.activo = False
        self.modelo.save()
        r = self.client.post(self.url("modelos"), {"rapido-nuevo_padre": "Samsung", "rapido-nombre": "Galaxy A14",
                                                   "rapido-tipo": "celular"})
        self.assertContains(r, "está desactivado")

    def test_seccion_sin_alta_rapida(self):
        self.assertEqual(self.client.get(self.url("metodos-pago")).status_code, 404)


class EliminarTests(Base):
    def test_catalogo_sin_uso_se_elimina(self):
        marca = Marca.objects.create(nombre="Sin uso")
        r = self.client.post(reverse("web:catalogo_editar", args=["marcas", marca.pk]), {"accion": "eliminar"})
        self.assertRedirects(r, reverse("web:catalogo", args=["marcas"]))
        self.assertFalse(Marca.objects.filter(pk=marca.pk).exists())

    def test_catalogo_en_uso_no_se_elimina(self):
        url = reverse("web:catalogo_editar", args=["reparaciones", self.reparacion.pk])
        self.orden()                                                  # la reparación está en una orden
        r = self.client.post(url, {"accion": "eliminar"}, follow=True)
        self.assertContains(r, "no se puede eliminar")
        self.assertTrue(Reparacion.objects.filter(pk=self.reparacion.pk).exists())

    def test_producto(self):
        r = self.client.post(reverse("web:producto_detalle", args=[self.cable.pk]), {"accion": "eliminar"})
        self.assertRedirects(r, reverse("web:productos"))
        self.assertFalse(Producto.objects.filter(pk=self.cable.pk).exists())


class DevolverReparacionTests(Base):
    def orden_pagada(self):
        o = self.orden("15000", pagado="55000")
        equipo = o.equipos.get()
        self.pantalla = LineaReparacion.objects.create(equipo=equipo, reparacion=self.revision, precio_vendido=D("40000"))
        self.bateria = equipo.lineas_reparacion.exclude(pk=self.pantalla.pk).get()
        return o

    def test_ver_las_reparaciones_de_la_orden(self):
        o = self.orden_pagada()
        r = self.client.get(reverse("web:reparaciones_para_devolver"), {"orden_buscar": f"#{o.id}"})
        self.assertContains(r, "se le devuelven <b>$ 15.000</b>")
        self.assertContains(r, "se le devuelven <b>$ 40.000</b>")
        r = self.client.get(reverse("web:reparaciones_para_devolver"), {"orden_buscar": "999"})
        self.assertContains(r, "No hay ninguna orden #999")

    def test_desde_la_orden_viene_elegida(self):
        o = self.orden_pagada()
        r = self.client.get(reverse("web:orden_detalle", args=[o.id]))
        self.assertContains(r, f"?orden={o.id}&amp;linea={self.bateria.id}")
        r = self.client.get(reverse("web:devoluciones"), {"orden": o.id, "linea": self.bateria.id})
        self.assertContains(r, f'value="{self.bateria.id}" checked')

    def test_devolver_ahora(self):
        o = self.orden_pagada()
        r = self.client.post(reverse("web:devoluciones"), {
            "accion": "devolver_reparacion", "orden": o.id, "linea": self.bateria.id,
            "dr-metodo_pago": self.efectivo.id, "nota": "No quiso la batería"})
        self.assertRedirects(r, reverse("web:devoluciones"))
        dev = Devolucion.objects.get()
        self.assertTrue(dev.devuelta)
        self.assertEqual(dev.monto, D("15000"))
        self.assertEqual(o.total, D("40000"))
        r = self.client.get(reverse("web:orden_detalle", args=[o.id]))
        self.assertContains(r, "Devuelta")                            # sigue anotada en la orden

    def test_devolver_y_dejar_pendiente(self):
        o = self.orden_pagada()
        self.client.post(reverse("web:devoluciones"), {
            "accion": "devolver_reparacion", "orden": o.id, "linea": self.bateria.id, "dr-metodo_pago": ""})
        self.assertFalse(Devolucion.objects.get().devuelta)
        self.assertContains(self.client.get(reverse("web:devoluciones")), "Marcar devuelta")

    def test_sin_dinero_de_mas_avisa(self):
        o = self.orden("15000", pagado="10000")
        LineaReparacion.objects.create(equipo=o.equipos.get(), reparacion=self.revision, precio_vendido=D("40000"))
        linea = o.equipos.get().lineas_reparacion.first()
        r = self.client.post(reverse("web:devoluciones"), {
            "accion": "devolver_reparacion", "orden": o.id, "linea": linea.id}, follow=True)
        self.assertContains(r, "No hay dinero para devolver")
        self.assertFalse(Devolucion.objects.exists())


class FilasYSaldoTests(Base):
    def datos_venta(self, **cambios):
        datos = {
            "prod-TOTAL_FORMS": "2", "prod-INITIAL_FORMS": "0", "prod-MIN_NUM_FORMS": "1", "prod-MAX_NUM_FORMS": "1000",
            "prod-0-producto": self.cable.id, "prod-0-cantidad_adquirida": "", "prod-0-precio_vendido": "",
            "prod-1-producto": "", "prod-1-cantidad_adquirida": "0", "prod-1-precio_vendido": "",
            "pago-TOTAL_FORMS": "1", "pago-INITIAL_FORMS": "0", "pago-MIN_NUM_FORMS": "1", "pago-MAX_NUM_FORMS": "1000",
            "pago-0-metodo_pago": self.efectivo.id, "pago-0-monto": "", "pago-0-recargo_porcentaje": "",
            "cliente": "",
        }
        datos.update(cambios)
        return datos

    def test_una_sola_fila_y_sin_1_por_defecto(self):
        r = self.client.get(reverse("web:venta_rapida"))
        self.assertContains(r, 'name="prod-TOTAL_FORMS" value="1"')
        self.assertContains(r, 'name="pago-TOTAL_FORMS" value="1"')
        self.assertNotContains(r, 'name="prod-0-cantidad_adquirida" value="1"')
        self.assertNotContains(r, 'placeholder="1"')
        self.assertContains(r, "+ Agregar otro producto")
        self.assertContains(r, 'data-precio="2500.00"')    # para mostrar el precio de lista

    def test_cantidad_vacia_es_1_y_fila_sin_producto_se_ignora(self):
        r = self.client.post(reverse("web:venta_rapida"), self.datos_venta())
        self.assertRedirects(r, reverse("web:venta_rapida"))
        venta = Venta.objects.get()
        self.assertEqual(venta.lineas_producto.get().cantidad_adquirida, 1)
        self.assertEqual(venta.total, D("2500"))

    def test_orden_sin_precio_no_dice_saldado(self):
        o = self.orden("0")
        self.assertContains(self.client.get(reverse("web:inicio")), "Sin precio todavía")
        self.assertContains(self.client.get(reverse("web:orden_detalle", args=[o.id])), "Sin precio todavía")
        self.assertNotContains(self.client.get(reverse("web:orden_detalle", args=[o.id])), "Saldado")


class PlantillasTests(Base):
    def test_sin_comentarios_de_varias_lineas(self):
        """{# #} de Django vale en UNA línea: si sigue en otra, se imprime como texto en la pantalla
        (pasó dos veces, y una vez un "<template>" del comentario escondió media página)."""
        from pathlib import Path
        carpeta = Path(__file__).resolve().parent.parent / "templates"
        for plantilla in carpeta.rglob("*.html"):
            for numero, linea in enumerate(plantilla.read_text().splitlines(), start=1):
                partes = linea.split("{#")[1:]
                with self.subTest(plantilla=plantilla.name, linea=numero):
                    self.assertTrue(all("#}" in p for p in partes), "usá {% comment %} para varias líneas")
