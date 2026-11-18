"""Pedidos del dueño del 18/11/2026: Estado de la orden con botones claros, borrar lo cargado por
error (como en el admin), tipos de equipo en el Catálogo y textos explícitos."""
from decimal import Decimal

from django.urls import reverse

from catalogo.models import Cliente, Devolucion, OrdenTrabajo, Pago, TipoEquipo, Venta
from catalogo.servicios import registrar_devolucion, vender_directo
from catalogo.models import LineaProductoVenta
from web.templatetags.formato import pista
from web.tests.test_pantallas import Base

D = Decimal


class EstadoDeLaOrdenTests(Base):
    def url(self, orden):
        return reverse("web:orden_detalle", args=[orden.id])

    def test_botones_claros_y_siguiente_paso(self):
        o = self.orden("1000")
        r = self.client.get(self.url(o))
        self.assertContains(r, "Estado de la orden")
        self.assertContains(r, "Ya está arreglado")
        self.assertContains(r, "No tenía falla")
        self.assertContains(r, "No tiene arreglo")
        self.client.post(self.url(o), {"accion": "estado", "equipo": o.equipos.get().id, "estado": "arreglado"})
        r = self.client.get(self.url(o))
        self.assertContains(r, "Cobrar $ 1.000 y entregar")
        self.assertContains(r, "volver a «en revisión»")

    def test_devolver_lo_que_sobra_desde_la_orden(self):
        o = self.orden("1000", estado="arreglado", pagado="1500")
        registrar_devolucion(o, monto=D("200"))                     # 200 anotados, sin hacer
        r = self.client.get(self.url(o))
        self.assertContains(r, "Ya le devolví $ 500")
        self.client.post(self.url(o), {"accion": "devolver_saldo", "dv-metodo_pago": self.efectivo.id})
        o = OrdenTrabajo.objects.get(pk=o.pk)
        self.assertEqual(o.monto_adeudado, D("0"))
        self.assertContains(self.client.get(self.url(o)), "Entregar al cliente")

    def test_entregar_avisa_si_falta_devolver(self):
        o = self.orden("1000", estado="arreglado", pagado="1500")
        r = self.client.get(reverse("web:orden_entregar", args=[o.id]))
        self.assertContains(r, "Antes de entregar hay que devolverle")

    def test_sin_arreglo_se_devuelve_el_equipo_y_se_cierra(self):
        o = self.orden("1000", estado="no_arreglable")              # sin seña: no queda dinero
        self.assertEqual(o.estado, "finalizada")
        self.assertContains(self.client.get(self.url(o)), "Devolver el equipo al cliente")
        self.assertContains(self.client.get(reverse("web:entregar")), f"#{o.id}<")
        r = self.client.post(reverse("web:orden_entregar", args=[o.id]), {"metodo_pago": ""}, follow=True)
        self.assertContains(r, "se le devolvió el equipo al cliente")
        o = OrdenTrabajo.objects.get(pk=o.id)
        self.assertEqual(o.estado, "cerrada")
        self.assertEqual(o.venta.total, D("0"))
        self.assertEqual(pista(o), ["hecho", "hecho", "hecho", "actual"])     # la pista llega al final

    def test_sin_arreglo_con_sena_primero_se_devuelve(self):
        o = self.orden("1000", estado="no_arreglable", pagado="400")
        self.assertContains(self.client.get(self.url(o)), "Ya le devolví $ 400")
        self.client.post(self.url(o), {"accion": "devolver_saldo", "dv-metodo_pago": self.efectivo.id})
        self.assertContains(self.client.get(self.url(o)), "Devolver el equipo al cliente")


class BorrarDesdeLasPantallasTests(Base):
    def test_quitar_pago_y_anular_devolucion(self):
        o = self.orden("1000", pagado="400")
        pago = o.pagos.get()
        dev = registrar_devolucion(o, monto=D("100"))
        url = reverse("web:orden_detalle", args=[o.id])
        self.client.post(url, {"accion": "anular_devolucion", "devolucion": dev.id})
        self.assertFalse(Devolucion.objects.exists())
        self.client.post(url, {"accion": "quitar_pago", "pago": pago.id})
        self.assertFalse(Pago.objects.exists())

    def test_eliminar_orden(self):
        o = self.orden("1000")
        r = self.client.post(reverse("web:orden_detalle", args=[o.id]), {"accion": "eliminar_orden"})
        self.assertRedirects(r, reverse("web:ordenes"))
        self.assertFalse(OrdenTrabajo.objects.exists())

    def test_eliminar_orden_con_pagos_no(self):
        o = self.orden("1000", pagado="100")
        r = self.client.post(reverse("web:orden_detalle", args=[o.id]), {"accion": "eliminar_orden"}, follow=True)
        self.assertContains(r, "tiene pagos o devoluciones")
        self.assertTrue(OrdenTrabajo.objects.exists())

    def test_anular_venta_directa(self):
        venta = vender_directo([LineaProductoVenta(producto=self.cable, cantidad_adquirida=1)],
                               [Pago(metodo_pago=self.efectivo, monto=self.cable.precio_venta)])
        r = self.client.post(reverse("web:venta_detalle", args=[venta.id]), {"accion": "anular_venta"})
        self.assertRedirects(r, reverse("web:ventas"))
        self.assertFalse(Venta.objects.exists())

    def test_eliminar_cliente(self):
        nuevo = Cliente.objects.create(nombre="Cargado por error")
        r = self.client.post(reverse("web:cliente_detalle", args=[nuevo.id]), {"accion": "eliminar_cliente"})
        self.assertRedirects(r, reverse("web:clientes"))
        self.orden()                                                # Juan tiene una orden: no se borra
        r = self.client.post(reverse("web:cliente_detalle", args=[self.juan.id]), {"accion": "eliminar_cliente"},
                             follow=True)
        self.assertContains(r, "Tiene órdenes o ventas")


class CatalogoClaroTests(Base):
    def test_tipos_de_equipo_en_el_catalogo(self):
        r = self.client.get(reverse("web:catalogo", args=["tipos-equipo"]))
        self.assertContains(r, "Agregar tipo de equipo")
        for grupo in ("Equipos", "Reparaciones", "Productos", "Pagos"):
            self.assertContains(r, grupo)
        self.client.post(reverse("web:catalogo", args=["tipos-equipo"]), {"nuevo-nombre": "Tablet"})
        tablet = TipoEquipo.objects.get(nombre="Tablet")
        self.assertEqual(tablet.clave, "tablet")
        self.assertContains(self.client.get(reverse("web:orden_nueva")), f'value="{tablet.clave}">Tablet<')

    def test_alta_rapida_de_tipo(self):
        r = self.client.post(reverse("web:alta_rapida", args=["tipos-equipo"]), {"rapido-nombre": "Consola"})
        self.assertIn("HX-Trigger", r)
        self.assertTrue(TipoEquipo.objects.filter(nombre="Consola").exists())

    def test_dialogo_de_modelo_con_marca_nueva_escondida(self):
        r = self.client.get(reverse("web:alta_rapida", args=["modelos"]))
        self.assertContains(r, "+ Escribir una marca nueva")
        self.assertContains(r, "data-escribir-padre hidden")
        self.assertContains(r, "Agregar modelo de equipo")


class VentaYRegistroTests(Base):
    def datos_venta(self, **cambios):
        from catalogo.models import MetodoPago
        credito = MetodoPago.objects.create(nombre="Crédito", cuenta="digital", recargo_porcentaje=D("15"))
        datos = {
            "prod-TOTAL_FORMS": "1", "prod-INITIAL_FORMS": "0", "prod-MIN_NUM_FORMS": "1", "prod-MAX_NUM_FORMS": "1000",
            "prod-0-producto": self.cable.id, "prod-0-cantidad_adquirida": "", "prod-0-precio_vendido": "18000",
            "pago-TOTAL_FORMS": "1", "pago-INITIAL_FORMS": "0", "pago-MIN_NUM_FORMS": "1", "pago-MAX_NUM_FORMS": "1000",
            "pago-0-metodo_pago": credito.id, "pago-0-monto": "", "pago-0-recargo_porcentaje": "", "cliente": "",
        }
        datos.update(cambios)
        return datos

    def test_resumen_muestra_el_recargo(self):
        r = self.client.post(reverse("web:venta_rapida_resumen"), self.datos_venta())
        self.assertContains(r, "Recargo Crédito (15 %)")
        self.assertContains(r, "+ $ 2.700")
        self.assertContains(r, "El cliente paga")
        self.assertContains(r, "$ 20.700")

    def test_registro_de_ventas(self):
        self.client.post(reverse("web:venta_rapida"), self.datos_venta())
        r = self.client.get(reverse("web:ventas"))
        self.assertContains(r, "Registro de ventas")
        self.assertContains(r, "Crédito")                           # con qué se cobró
        self.assertContains(r, "$ 20.700")                          # cobrado con recargo
        self.assertContains(r, "Entró en digital")


class PedidosDeLaTardeTests(Base):
    """Revisión una sola vez, registro con tipo y productos, impresión y Configuración."""

    def test_revision_solo_en_la_primera_fila(self):
        r = self.client.get(reverse("web:orden_nueva"))
        html = r.content.decode()
        fila_vacia = html[html.index("<template data-fila-vacia>"):html.index("</template>")]
        self.assertNotIn("Revisión / diagnóstico", fila_vacia)           # las filas que se agregan no la ofrecen
        self.assertIn(f'<option value="{self.revision.id}" selected>', html)  # la primera sí

    def test_revision_no_se_agrega_dos_veces(self):
        from catalogo.models import LineaReparacion
        o = self.orden("1000")
        LineaReparacion.objects.create(equipo=o.equipos.get(), reparacion=self.revision, precio_vendido=D("0"))
        url = reverse("web:orden_detalle", args=[o.id])
        html = self.client.get(url).content.decode()
        agregar = html[html.index("Agregar reparación a este equipo"):]
        self.assertNotIn(f'value="{self.revision.id}"', agregar[:agregar.index("</select>")])
        r = self.client.post(url, {"accion": "reparacion", "equipo": o.equipos.get().id,
                                   "rep-reparacion": self.revision.id, "rep-precio_vendido": "0"}, follow=True)
        self.assertContains(r, "va una sola vez")

    def test_registro_dice_el_tipo_y_los_productos_de_la_orden(self):
        from catalogo.models import LineaProductoOrden
        from catalogo.servicios import cambiar_estado_equipo, entregar_orden
        o = self.orden("1000", estado="arreglado")
        LineaProductoOrden.objects.create(orden_trabajo=o, producto=self.cable, cantidad_adquirida=2, precio_vendido=D("100"))
        entregar_orden(o, self.efectivo)
        r = self.client.get(reverse("web:ventas"))
        self.assertContains(r, f"Orden #{o.id}</a>")
        self.assertContains(r, "Productos: 2× Cable USB-C")

    def test_menu_de_impresion_y_comprobante(self):
        o = self.orden("1000")
        r = self.client.get(reverse("web:orden_detalle", args=[o.id]))
        self.assertContains(r, "Imprimir la orden")
        self.assertContains(r, "Imprimir comprobante para el cliente")
        self.assertContains(r, "Pasados 30 días")

    def test_configuracion(self):
        r = self.client.get(reverse("web:catalogo_inicio"))
        self.assertContains(r, "<h1>Configuración</h1>")
        self.assertContains(r, ">Configuración</span>")              # en el menú
