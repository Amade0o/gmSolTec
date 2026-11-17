"""Pantallas de la etapa 7: lista, nueva orden, detalle, entregar, venta rápida y devoluciones."""
from decimal import Decimal

from django.contrib.messages import get_messages
from django.urls import reverse

from catalogo.models import (
    CategoriaProducto, CategoriaReparacion, Cliente, Devolucion, EquipoRecibido, LineaReparacion,
    OrdenTrabajo, Pago, Producto, Reparacion, Venta,
)
from catalogo.servicios import cerrar_orden
from web.tests.test_inicio import DatosBase

D = Decimal


def textos(respuesta):
    return [str(m) for m in get_messages(respuesta.wsgi_request)]


class Base(DatosBase):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.revision = Reparacion.objects.create(
            nombre="Revisión / diagnóstico", categoria=CategoriaReparacion.objects.create(nombre="Revisión"))
        self.cable = Producto.objects.create(
            nombre="Cable USB-C", categoria=CategoriaProducto.objects.create(nombre="Cables"),
            precio_compra=D("1000"), precio_venta=D("2500"))


class LoginTests(Base):
    def test_todas_piden_login(self):
        self.client.logout()
        orden = self.orden()
        for url in (reverse("web:ordenes"), reverse("web:orden_nueva"), reverse("web:orden_detalle", args=[orden.id]),
                    reverse("web:orden_entregar", args=[orden.id]), reverse("web:entregar"),
                    reverse("web:venta_rapida"), reverse("web:devoluciones")):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.post(reverse("web:orden_nueva_resumen")).status_code, 302)


class ListaTests(Base):
    def test_filtros(self):
        en_revision = self.orden()
        lista = self.orden(estado="arreglado", pagado="1000")
        r = self.client.get(reverse("web:ordenes"))
        self.assertContains(r, f"#{en_revision.id}<")
        self.assertContains(r, f"#{lista.id}<")
        r = self.client.get(reverse("web:ordenes") + "?estado=lista")
        self.assertNotContains(r, f"#{en_revision.id}<")
        self.assertContains(r, f"#{lista.id}<")
        cerrar_orden(lista)
        r = self.client.get(reverse("web:ordenes") + "?estado=cerrada")
        self.assertContains(r, f"#{lista.id}<")
        self.assertContains(r, "Venta #")

    def test_buscar_por_numero_abre_la_orden(self):
        o = self.orden()
        r = self.client.get(reverse("web:ordenes") + f"?q=%23{o.id}")
        self.assertRedirects(r, reverse("web:orden_detalle", args=[o.id]))

    def test_buscar_por_cliente(self):
        o = self.orden()
        otro = OrdenTrabajo.objects.create(cliente=Cliente.objects.create(nombre="Ana Torres"))
        r = self.client.get(reverse("web:ordenes") + "?estado=todas&q=pérez")
        self.assertContains(r, f"#{o.id}<")
        self.assertNotContains(r, f"#{otro.id}<")


class NuevaOrdenTests(Base):
    def datos(self, **cambios):
        datos = {
            "cli-cliente": "", "cli-nuevo_nombre": "Lucía Fernández", "cli-nuevo_telefono": "3584555555",
            "eq-tipo": "celular", "eq-modelo": self.modelo.id, "eq-problema": "Pantalla rota",
            "eq-tipo_bloqueo": "patron", "eq-clave_bloqueo": "1-5-9-6", "eq-accesorios_dejados": "",
            "rep-TOTAL_FORMS": "3", "rep-INITIAL_FORMS": "0", "rep-MIN_NUM_FORMS": "1", "rep-MAX_NUM_FORMS": "1000",
            "rep-0-reparacion": self.reparacion.id, "rep-0-precio_vendido": "42500",
            "rep-1-reparacion": "", "rep-1-precio_vendido": "",
            "rep-2-reparacion": "", "rep-2-precio_vendido": "",
            "prod-TOTAL_FORMS": "2", "prod-INITIAL_FORMS": "0", "prod-MIN_NUM_FORMS": "0", "prod-MAX_NUM_FORMS": "1000",
            "prod-0-producto": self.cable.id, "prod-0-cantidad_adquirida": "1", "prod-0-precio_vendido": "",
            "prod-1-producto": "", "prod-1-cantidad_adquirida": "1", "prod-1-precio_vendido": "",
            "sena-metodo_pago": self.efectivo.id, "sena-monto": "20000", "sena-recargo_porcentaje": "",
        }
        datos.update(cambios)
        return datos

    def test_pantalla_viene_con_revision_cargada(self):
        r = self.client.get(reverse("web:orden_nueva"))
        self.assertContains(r, "El número se asigna al guardar")
        self.assertContains(r, f'<option value="{self.revision.id}" selected>')

    def test_crea_la_orden_con_cliente_nuevo(self):
        r = self.client.post(reverse("web:orden_nueva"), self.datos())
        orden = OrdenTrabajo.objects.get(cliente__nombre="Lucía Fernández")
        self.assertRedirects(r, reverse("web:orden_detalle", args=[orden.id]))
        self.assertEqual(orden.total, D("45000"))              # 42500 + cable 2500
        self.assertEqual(orden.monto_pagado, D("20000"))
        self.assertEqual(orden.equipos.get().clave_bloqueo, "1-5-9-6")
        self.assertTrue(orden.cliente.telefonos.get().principal)

    def test_cliente_existente_y_sin_sena(self):
        datos = self.datos(**{"cli-cliente": self.juan.id, "cli-nuevo_nombre": "", "cli-nuevo_telefono": "",
                              "sena-metodo_pago": "", "sena-monto": ""})
        self.client.post(reverse("web:orden_nueva"), datos)
        orden = OrdenTrabajo.objects.get(cliente=self.juan)
        self.assertEqual(orden.pagos.count(), 0)

    def test_sin_cliente_no_guarda(self):
        r = self.client.post(reverse("web:orden_nueva"), self.datos(**{"cli-nuevo_nombre": ""}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Falta el cliente")
        self.assertEqual(OrdenTrabajo.objects.count(), 0)

    def test_sena_de_mas_no_guarda_ni_el_cliente_nuevo(self):
        r = self.client.post(reverse("web:orden_nueva"), self.datos(**{"sena-monto": "99999"}))
        self.assertEqual(r.status_code, 200)
        self.assertIn("El pago supera lo que falta pagar de la orden.", textos(r))
        self.assertEqual(OrdenTrabajo.objects.count(), 0)
        self.assertFalse(Cliente.objects.filter(nombre="Lucía Fernández").exists())

    def test_patron_mal_escrito(self):
        r = self.client.post(reverse("web:orden_nueva"), self.datos(**{"eq-clave_bloqueo": "1-1-2"}))
        self.assertContains(r, "no repite puntos")
        r = self.client.post(reverse("web:orden_nueva"), self.datos(**{"eq-tipo_bloqueo": "pin", "eq-clave_bloqueo": "12a4"}))
        self.assertContains(r, "solo números")

    def test_resumen_en_vivo(self):
        r = self.client.post(reverse("web:orden_nueva_resumen"), self.datos())
        self.assertContains(r, "$ 45.000")
        self.assertContains(r, "Debe $ 25.000")


class DetalleTests(Base):
    def accion(self, orden, **datos):
        return self.client.post(reverse("web:orden_detalle", args=[orden.id]), datos)

    def test_muestra_la_orden(self):
        o = self.orden("42500")
        r = self.client.get(reverse("web:orden_detalle", args=[o.id]))
        self.assertContains(r, f"Orden #{o.id}")
        self.assertContains(r, "Debe $ 42.500")
        self.assertContains(r, "Módulo OLED")

    def test_cambiar_estado_del_equipo(self):
        o = self.orden()
        r = self.accion(o, accion="estado", equipo=o.equipos.get().id, estado="arreglado")
        self.assertRedirects(r, reverse("web:orden_detalle", args=[o.id]))
        self.assertEqual(o.estado, "lista")

    def test_no_toca_equipos_de_otra_orden(self):
        o, otra = self.orden(), self.orden()
        r = self.accion(o, accion="estado", equipo=otra.equipos.get().id, estado="arreglado")
        self.assertEqual(r.status_code, 404)

    def test_agregar_reparacion_producto_y_pago(self):
        o = self.orden("1000")
        equipo = o.equipos.get()
        self.accion(o, accion="reparacion", equipo=equipo.id, **{"rep-reparacion": self.revision.id, "rep-precio_vendido": "500"})
        self.accion(o, accion="producto", **{"prod-producto": self.cable.id, "prod-cantidad_adquirida": "2", "prod-precio_vendido": ""})
        self.accion(o, accion="pago", **{"pago-metodo_pago": self.efectivo.id, "pago-monto": "1000", "pago-recargo_porcentaje": ""})
        self.assertEqual(o.total, D("6500"))
        self.assertEqual(o.monto_pagado, D("1000"))

    def test_pago_de_mas_muestra_el_error(self):
        o = self.orden("1000")
        r = self.accion(o, accion="pago", **{"pago-metodo_pago": self.efectivo.id, "pago-monto": "5000"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("El pago supera lo que falta pagar de la orden.", textos(r))
        self.assertEqual(o.pagos.count(), 0)

    def test_quitar_la_unica_reparacion_no(self):
        o = self.orden()
        r = self.accion(o, accion="quitar_reparacion", linea=LineaReparacion.objects.get(equipo__orden_trabajo=o).id)
        self.assertIn("El equipo tiene que quedar con al menos una reparación.", textos(r))

    def test_agregar_otro_equipo(self):
        o = self.orden()
        self.accion(o, accion="equipo", **{
            "eq-tipo": "pc", "eq-problema": "No prende", "eq-tipo_bloqueo": "ninguno", "eq-clave_bloqueo": "",
            "eqrep-reparacion": self.revision.id, "eqrep-precio_vendido": "0"})
        self.assertEqual(o.equipos.count(), 2)

    def test_registrar_devolucion_de_una_reparacion(self):
        o = self.orden("1000", pagado="1000", estado="no_arreglable")
        linea = LineaReparacion.objects.get(equipo__orden_trabajo=o)
        self.accion(o, accion="devolucion", **{"dev-linea_reparacion": linea.id, "dev-monto": "", "dev-nota": ""})
        devolucion = o.devoluciones.get()
        self.assertEqual(devolucion.monto, D("1000"))
        self.assertFalse(devolucion.devuelta)               # paso 1: solo se registra

    def test_orden_cerrada_es_de_solo_lectura(self):
        o = self.orden("1000", estado="arreglado", pagado="1000")
        cerrar_orden(o)
        r = self.client.get(reverse("web:orden_detalle", args=[o.id]))
        self.assertContains(r, "Entregada")
        self.assertNotContains(r, "Registrar pago")
        r = self.accion(o, accion="estado", equipo=o.equipos.get().id, estado="pendiente")
        self.assertIn("La orden ya está cerrada: no se puede modificar.", textos(r))


class EntregarTests(Base):
    def test_lista_de_entregas(self):
        lista = self.orden(estado="arreglado")
        pendiente = self.orden()
        r = self.client.get(reverse("web:entregar"))
        self.assertContains(r, f"#{lista.id}<")
        self.assertNotContains(r, f"#{pendiente.id}<")
        r = self.client.get(reverse("web:entregar") + "?q=pérez")
        self.assertContains(r, f"#{pendiente.id}<")         # buscando aparecen todas las abiertas

    def test_menu_marca_la_seccion_correcta(self):
        ordenes = reverse("web:ordenes")
        r = self.client.get(reverse("web:entregar"))
        self.assertNotContains(r, f'href="{ordenes}" class="on"')
        r = self.client.get(ordenes)
        self.assertContains(r, f'href="{ordenes}" class="on" aria-current="page"')
        r = self.client.get(reverse("web:orden_nueva"))         # subpantalla: marca la sección, no "esta página"
        self.assertContains(r, f'href="{ordenes}" class="on" aria-current="true"')
        self.assertContains(r, f'href="{reverse("web:inicio")}"><svg', count=1)  # Inicio, sin marcar

    def test_cobra_el_saldo_y_entrega(self):
        o = self.orden("1000", estado="arreglado", pagado="400")
        url = reverse("web:orden_entregar", args=[o.id])
        self.assertContains(self.client.get(url), "Cobrar $ 600 y entregar")
        r = self.client.post(url, {"metodo_pago": self.efectivo.id, "recargo_porcentaje": ""})
        self.assertRedirects(r, reverse("web:orden_detalle", args=[o.id]))
        self.assertTrue(Venta.objects.filter(orden_trabajo=o).exists())
        self.assertEqual(o.pagos.count(), 2)

    def test_sin_metodo_no_entrega(self):
        o = self.orden("1000", estado="arreglado")
        r = self.client.post(reverse("web:orden_entregar", args=[o.id]), {"metodo_pago": ""})
        self.assertIn("Elegí con qué método paga el saldo.", textos(r))
        self.assertFalse(Venta.objects.exists())

    def test_pendiente_no_se_entrega(self):
        o = self.orden()
        r = self.client.get(reverse("web:orden_entregar", args=[o.id]))
        self.assertContains(r, "todavía no se puede entregar")


class VentaRapidaTests(Base):
    def datos(self, **cambios):
        datos = {
            "prod-TOTAL_FORMS": "3", "prod-INITIAL_FORMS": "0", "prod-MIN_NUM_FORMS": "1", "prod-MAX_NUM_FORMS": "1000",
            "prod-0-producto": self.cable.id, "prod-0-cantidad_adquirida": "2", "prod-0-precio_vendido": "",
            "prod-1-producto": "", "prod-1-cantidad_adquirida": "1", "prod-1-precio_vendido": "",
            "prod-2-producto": "", "prod-2-cantidad_adquirida": "1", "prod-2-precio_vendido": "",
            "pago-TOTAL_FORMS": "2", "pago-INITIAL_FORMS": "0", "pago-MIN_NUM_FORMS": "1", "pago-MAX_NUM_FORMS": "1000",
            "pago-0-metodo_pago": self.efectivo.id, "pago-0-monto": "", "pago-0-recargo_porcentaje": "",
            "pago-1-metodo_pago": "", "pago-1-monto": "", "pago-1-recargo_porcentaje": "",
            "cliente": "",
        }
        datos.update(cambios)
        return datos

    def test_monto_vacio_cobra_el_total(self):
        r = self.client.post(reverse("web:venta_rapida"), self.datos())
        self.assertRedirects(r, reverse("web:venta_rapida"))
        venta = Venta.objects.get()
        self.assertEqual(venta.total, D("5000"))
        self.assertEqual(venta.pagos.get().monto, D("5000"))

    def test_dos_pagos_y_cliente(self):
        self.client.post(reverse("web:venta_rapida"), self.datos(**{
            "pago-0-monto": "2000", "pago-1-metodo_pago": self.efectivo.id, "cliente": self.juan.id}))
        venta = Venta.objects.get()
        self.assertEqual(venta.cliente, self.juan)
        self.assertEqual(sorted(p.monto for p in venta.pagos.all()), [D("2000"), D("3000")])

    def test_pagos_que_no_suman_no_guardan(self):
        r = self.client.post(reverse("web:venta_rapida"), self.datos(**{"pago-0-monto": "100"}))
        self.assertIn("Los pagos deben sumar exactamente el total de la venta.", textos(r))
        self.assertFalse(Venta.objects.exists())

    def test_resumen(self):
        r = self.client.post(reverse("web:venta_rapida_resumen"), self.datos())
        self.assertContains(r, "$ 5.000")
        self.assertContains(r, "Falta asignar $ 5.000")


class ElegirClienteTests(Base):
    """Nueva orden y Venta rápida: buscador + últimos clientes atendidos (sin el desplegable con todos)."""

    def test_sin_buscar_muestra_los_ultimos_atendidos(self):
        viejo = Cliente.objects.create(nombre="Cliente Sin Ordenes")
        self.orden()                                   # Juan Pérez tiene una orden: aparece primero
        r = self.client.get(reverse("web:orden_nueva"))
        self.assertContains(r, 'name="cli-cliente" value=""')
        self.assertContains(r, f'name="cli-cliente" value="{self.juan.id}"')
        self.assertContains(r, "Últimos clientes atendidos")
        self.assertContains(r, viejo.nombre)           # completa con los últimos cargados

    def test_desde_la_ficha_viene_elegido(self):
        r = self.client.get(reverse("web:orden_nueva") + f"?cliente={self.juan.id}")
        self.assertContains(r, f'name="cli-cliente" value="{self.juan.id}" checked')

    def test_buscar(self):
        Cliente.objects.create(nombre="María Gómez")
        url = reverse("web:buscar_clientes")
        r = self.client.get(url, {"campo": "cliente", "buscar_cliente": "maría"})
        self.assertContains(r, "María Gómez")
        self.assertNotContains(r, "Juan Pérez")
        self.assertContains(r, 'name="cliente" value=""')       # "Sin cliente" siempre está
        r = self.client.get(url, {"campo": "cliente", "buscar_cliente": "nadie"})
        self.assertContains(r, "No hay clientes con")
        # el elegido no se pierde aunque no coincida con lo buscado
        r = self.client.get(url, {"campo": "cliente", "buscar_cliente": "maría", "cliente": self.juan.id})
        self.assertContains(r, f'value="{self.juan.id}" checked')

    def test_buscar_campo_desconocido(self):
        r = self.client.get(reverse("web:buscar_clientes"), {"campo": "otro"})
        self.assertEqual(r.status_code, 404)

    def test_venta_rapida_no_lista_todos_los_clientes(self):
        for i in range(20):
            Cliente.objects.create(nombre=f"Otro {i:02d}")
        r = self.client.get(reverse("web:venta_rapida"))
        self.assertContains(r, 'class="opcion"', count=7)       # "Sin cliente" + 6
        self.assertNotContains(r, "<select name=\"cliente\"")


class DevolucionesTests(Base):
    def test_marcar_devuelta(self):
        o = self.orden("1000", pagado="400", estado="no_arreglable")
        d = Devolucion.objects.create(orden_trabajo=o, monto=D("400"))
        r = self.client.get(reverse("web:devoluciones"))
        self.assertContains(r, "Marcar devuelta")
        r = self.client.post(reverse("web:devoluciones"), {"devolucion": d.id, f"d{d.id}-metodo_pago": self.efectivo.id})
        self.assertRedirects(r, reverse("web:devoluciones"))
        self.assertTrue(Devolucion.objects.get(pk=d.id).devuelta)
        self.assertEqual(o.estado, "finalizada")

    def test_sin_metodo_no_se_marca(self):
        o = self.orden("1000", pagado="400", estado="no_arreglable")
        d = Devolucion.objects.create(orden_trabajo=o, monto=D("400"))
        r = self.client.post(reverse("web:devoluciones"), {"devolucion": d.id})
        self.assertIn("Elegí con qué método se devolvió el dinero.", textos(r))
        self.assertFalse(Devolucion.objects.get(pk=d.id).devuelta)

    def test_avisa_saldo_a_favor_sin_registrar(self):
        o = self.orden("1000", pagado="400", estado="no_arreglable")
        r = self.client.get(reverse("web:devoluciones"))
        self.assertContains(r, "sin devolución registrada")
        self.assertContains(r, f"#{o.id}<")
