from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from catalogo.models import (
    CategoriaProducto, CategoriaReparacion, Cliente, EquipoRecibido, LineaProductoOrden,
    LineaProductoVenta, LineaReparacion, Marca, MetodoPago, ModeloEquipo, OrdenTrabajo,
    Pago, Producto, Reparacion, Telefono, Venta,
)
from catalogo.servicios import ReglaDeNegocioError, cerrar_orden

D = Decimal


class Base(TestCase):
    def setUp(self):
        self.efectivo = MetodoPago.objects.create(nombre="Efectivo", cuenta="efectivo", recargo_porcentaje=D("0"))
        self.tarjeta = MetodoPago.objects.create(nombre="Tarjeta", cuenta="digital", recargo_porcentaje=D("15"))
        self.cliente = Cliente.objects.create(nombre="Juan")
        cat_rep = CategoriaReparacion.objects.create(nombre="Pantalla")
        self.reparacion = Reparacion.objects.create(nombre="Modulo", categoria=cat_rep)
        cat_prod = CategoriaProducto.objects.create(nombre="Cables")
        self.producto = Producto.objects.create(
            nombre="Cable USB", categoria=cat_prod, precio_compra=D("100"), precio_venta=D("250"))

    def crear_orden(self, precio=D("1000"), cant_producto=0):
        orden = OrdenTrabajo.objects.create(cliente=self.cliente)
        equipo = EquipoRecibido.objects.create(
            orden_trabajo=orden, tipo_id="celular", problema="No carga", tipo_bloqueo="ninguno")
        LineaReparacion.objects.create(equipo=equipo, reparacion=self.reparacion, precio_vendido=precio)
        if cant_producto:
            LineaProductoOrden.objects.create(
                orden_trabajo=orden, producto=self.producto,
                cantidad_adquirida=cant_producto, precio_vendido=D("250"))
        return orden

    def pagar(self, orden, monto, metodo=None):
        return Pago.objects.create(orden_trabajo=orden, metodo_pago=metodo or self.efectivo, monto=D(monto))


class ModeloTests(Base):
    def test_total_y_montos(self):
        orden = self.crear_orden(D("1000"), 2)
        self.assertEqual(orden.total, D("1500"))
        self.pagar(orden, "400", self.tarjeta)
        self.assertEqual(orden.monto_pagado, D("400"))
        self.assertEqual(orden.monto_adeudado, D("1100"))
        self.assertTrue(orden.adeuda)

    def test_recargo(self):
        pago = self.pagar(self.crear_orden(), "100", self.tarjeta)
        self.assertEqual(pago.recargo_porcentaje, D("15"))
        self.assertEqual(pago.total_cobrado, D("115"))

    def test_precio_se_copia_del_producto_si_viene_vacio(self):
        orden = self.crear_orden()
        linea = LineaProductoOrden(orden_trabajo=orden, producto=self.producto, cantidad_adquirida=2)
        linea.save()
        self.assertEqual(linea.precio_vendido, D("250"))
        self.assertEqual(linea.subtotal, D("500"))

    def test_precio_explicito_se_respeta(self):
        orden = self.crear_orden()
        linea = LineaProductoOrden.objects.create(
            orden_trabajo=orden, producto=self.producto, cantidad_adquirida=1, precio_vendido=D("100"))
        self.assertEqual(linea.precio_vendido, D("100"))

    def test_pago_no_supera_lo_adeudado(self):
        orden = self.crear_orden()   # total 1000
        pago = Pago(orden_trabajo=orden, metodo_pago=self.efectivo, monto=D("1500"))
        with self.assertRaises(ValidationError):
            pago.full_clean()

    def test_pago_justo_y_parcial_validos(self):
        orden = self.crear_orden()
        Pago(orden_trabajo=orden, metodo_pago=self.efectivo, monto=D("1000")).full_clean()
        self.pagar(orden, "400")
        Pago(orden_trabajo=orden, metodo_pago=self.efectivo, monto=D("600")).full_clean()
        with self.assertRaises(ValidationError):
            Pago(orden_trabajo=orden, metodo_pago=self.efectivo, monto=D("601")).full_clean()

    def test_editar_un_pago_existente_no_se_cuenta_dos_veces(self):
        orden = self.crear_orden()
        pago = self.pagar(orden, "1000")
        pago.full_clean()     # mismo monto, no debe fallar

    def test_sena_con_total_cero_se_permite(self):
        orden = OrdenTrabajo.objects.create(cliente=self.cliente)
        Pago(orden_trabajo=orden, metodo_pago=self.efectivo, monto=D("5000")).full_clean()

    def test_pago_con_orden_y_venta_invalido(self):
        venta = Venta.objects.create(total=D("100"))
        pago = Pago(orden_trabajo=self.crear_orden(), venta=venta, metodo_pago=self.efectivo, monto=D("10"))
        with self.assertRaises(ValidationError):
            pago.full_clean()

    def test_pago_sin_dueno_no_se_guarda(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Pago.objects.create(metodo_pago=self.efectivo, monto=D("100"))

    def test_pago_de_venta_directa(self):
        venta = Venta.objects.create(total=D("100"))
        pago = Pago(venta=venta, metodo_pago=self.efectivo, monto=D("100"))
        pago.full_clean()
        pago.save()
        self.assertFalse(pago.retenido)
        self.assertIn(f"Venta #{venta.id}", str(pago))

    def test_pago_monto_cero_invalido(self):
        with self.assertRaises(ValidationError):
            Pago(metodo_pago=self.efectivo, monto=D("0"), venta=Venta.objects.create(total=D("1"))).full_clean()

    def test_retenido(self):
        orden = self.crear_orden()
        pago = self.pagar(orden, "400")
        self.assertTrue(pago.retenido)
        self.assertEqual(orden.monto_retenido, D("400"))

    def test_nombres_unicos(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            MetodoPago.objects.create(nombre="Efectivo", cuenta="efectivo")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Marca.objects.create(nombre="A")
            Marca.objects.create(nombre="A")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Producto.objects.create(nombre="Cable USB", categoria=self.producto.categoria,
                                    precio_compra=1, precio_venta=2)

    def test_unicos_por_pareja(self):
        m1, m2 = Marca.objects.create(nombre="M1"), Marca.objects.create(nombre="M2")
        ModeloEquipo.objects.create(nombre="X", marca=m1, tipo_id="celular")
        ModeloEquipo.objects.create(nombre="X", marca=m2, tipo_id="celular")   # otra marca: ok
        with self.assertRaises(IntegrityError), transaction.atomic():
            ModeloEquipo.objects.create(nombre="X", marca=m1, tipo_id="celular")
        c2 = CategoriaReparacion.objects.create(nombre="Otra")
        Reparacion.objects.create(nombre="Modulo", categoria=c2)            # otra categoría: ok
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reparacion.objects.create(nombre="Modulo", categoria=self.reparacion.categoria)

    def test_clientes_y_telefonos_pueden_repetirse(self):
        Cliente.objects.create(nombre="Juan")
        c = Cliente.objects.create(nombre="Otro")
        Telefono.objects.create(cliente=self.cliente, numero="123")
        Telefono.objects.create(cliente=c, numero="123")

    def test_producto_precio_negativo_invalido(self):
        p = Producto(nombre="Raro", categoria=self.producto.categoria, precio_compra=D("-1"), precio_venta=D("5"))
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_ninguno_con_clave_invalido(self):
        orden = OrdenTrabajo.objects.create(cliente=self.cliente)
        e = EquipoRecibido(orden_trabajo=orden, tipo_id="celular", problema="x",
                           tipo_bloqueo="ninguno", clave_bloqueo="1234")
        with self.assertRaises(ValidationError) as ctx:
            e.full_clean()
        self.assertIn("clave_bloqueo", ctx.exception.message_dict)
        e.tipo_bloqueo = "pin"
        e.full_clean()


class CierreTests(Base):
    def lista_y_paga(self, pagado="1000"):
        orden = self.crear_orden()
        orden.equipos.update(estado="arreglado")
        self.pagar(orden, pagado)
        return orden

    def test_cierra(self):
        orden = self.lista_y_paga()
        venta = cerrar_orden(orden)
        self.assertEqual(venta.total, D("1000"))
        self.assertTrue(orden.cerrada)
        self.assertEqual(orden.estado, "cerrada")
        pago = orden.pagos.get()
        pago.refresh_from_db()
        self.assertFalse(pago.retenido)

    def test_no_cierra_con_deuda(self):
        with self.assertRaises(ReglaDeNegocioError):
            cerrar_orden(self.lista_y_paga("400"))

    def test_no_cierra_si_pago_de_mas(self):
        with self.assertRaises(ReglaDeNegocioError):
            cerrar_orden(self.lista_y_paga("1200"))     # creado por código, sin validar
        self.assertFalse(Venta.objects.exists())

    def test_no_cierra_pendiente_ni_no_arreglable_ni_dos_veces(self):
        o = self.crear_orden()
        self.pagar(o, "1000")
        with self.assertRaises(ReglaDeNegocioError):
            cerrar_orden(o)
        o.equipos.update(estado="no_arreglable")
        with self.assertRaises(ReglaDeNegocioError):
            cerrar_orden(o)
        o2 = self.lista_y_paga()
        cerrar_orden(o2)
        with self.assertRaises(ReglaDeNegocioError):
            cerrar_orden(o2)


class AdminTests(Base):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        User.objects.create_superuser("admin", "a@a.com", "pass")
        self.client.login(username="admin", password="pass")

    def test_todas_las_pantallas_cargan(self):
        orden = self.crear_orden(D("1000"), 1)
        self.pagar(orden, "100")
        venta = Venta.objects.create(total=D("10"))
        for modelo, obj in [("categoriaproducto", self.producto.categoria), ("marca", Marca.objects.create(nombre="Z")),
                            ("producto", self.producto), ("cliente", self.cliente),
                            ("categoriareparacion", self.reparacion.categoria), ("reparacion", self.reparacion),
                            ("metodopago", self.efectivo), ("ordentrabajo", orden),
                            ("equiporecibido", orden.equipos.first()), ("venta", venta)]:
            r = self.client.get(f"/admin/catalogo/{modelo}/")
            self.assertEqual(r.status_code, 200, f"lista {modelo}")
            r = self.client.get(f"/admin/catalogo/{modelo}/{obj.pk}/change/")
            self.assertEqual(r.status_code, 200, f"editar {modelo}")
            if modelo not in ("equiporecibido",):
                r = self.client.get(f"/admin/catalogo/{modelo}/add/")
                self.assertEqual(r.status_code, 200, f"agregar {modelo}")
        self.assertEqual(self.client.get("/admin/catalogo/pago/").status_code, 200)
        self.assertEqual(self.client.get("/admin/catalogo/pago/add/").status_code, 403)
        self.assertEqual(self.client.get("/admin/catalogo/equiporecibido/add/").status_code, 403)

    def test_lineas_sueltas_ya_no_existen(self):
        for m in ("lineareparacion", "lineaproductoorden", "lineaproductoventa"):
            self.assertEqual(self.client.get(f"/admin/catalogo/{m}/").status_code, 404)

    def datos_orden(self, orden, productos=(), pagos=()):
        e = orden.equipos.first()
        d = {
            "cliente": self.cliente.pk,
            "equipos-TOTAL_FORMS": "1", "equipos-INITIAL_FORMS": "1",
            "equipos-MIN_NUM_FORMS": "0", "equipos-MAX_NUM_FORMS": "1000",
            "equipos-0-id": e.pk, "equipos-0-orden_trabajo": orden.pk,
            "equipos-0-tipo": "celular", "equipos-0-problema": "No carga",
            "equipos-0-tipo_bloqueo": "ninguno", "equipos-0-clave_bloqueo": "",
            "equipos-0-accesorios_dejados": "", "equipos-0-estado": "pendiente",
            "lineas_producto-TOTAL_FORMS": str(len(productos)), "lineas_producto-INITIAL_FORMS": "0",
            "lineas_producto-MIN_NUM_FORMS": "0", "lineas_producto-MAX_NUM_FORMS": "1000",
            "pagos-TOTAL_FORMS": str(len(pagos)), "pagos-INITIAL_FORMS": "0",
            "pagos-MIN_NUM_FORMS": "0", "pagos-MAX_NUM_FORMS": "1000",
            "_save": "Guardar",
            "devoluciones-TOTAL_FORMS": "0", "devoluciones-INITIAL_FORMS": "0",
            "devoluciones-MIN_NUM_FORMS": "0", "devoluciones-MAX_NUM_FORMS": "1000",
        }
        for i, (prod, cant, precio) in enumerate(productos):
            d[f"lineas_producto-{i}-producto"] = prod
            d[f"lineas_producto-{i}-cantidad_adquirida"] = cant
            d[f"lineas_producto-{i}-precio_vendido"] = precio
        for i, (met, monto) in enumerate(pagos):
            d[f"pagos-{i}-metodo_pago"] = met
            d[f"pagos-{i}-monto"] = monto
            d[f"pagos-{i}-recargo_porcentaje"] = ""
        return d

    def test_admin_rechaza_producto_repetido(self):
        orden = self.crear_orden()
        datos = self.datos_orden(orden, productos=[(self.producto.pk, 1, ""), (self.producto.pk, 2, "")])
        r = self.client.post(f"/admin/catalogo/ordentrabajo/{orden.pk}/change/", datos)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "No repitas el mismo producto")
        self.assertEqual(orden.lineas_producto.count(), 0)

    def test_admin_copia_precio_y_guarda(self):
        orden = self.crear_orden()
        datos = self.datos_orden(orden, productos=[(self.producto.pk, 2, "")])
        r = self.client.post(f"/admin/catalogo/ordentrabajo/{orden.pk}/change/", datos)
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["errors"] if r.status_code == 200 else "")
        self.assertEqual(orden.lineas_producto.get().precio_vendido, D("250"))
        self.assertEqual(orden.total, D("1500"))

    def test_admin_rechaza_pago_de_mas_y_acepta_justo(self):
        orden = self.crear_orden()
        r = self.client.post(f"/admin/catalogo/ordentrabajo/{orden.pk}/change/",
                             self.datos_orden(orden, pagos=[(self.efectivo.pk, "9999")]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "supera lo que falta pagar")
        r = self.client.post(f"/admin/catalogo/ordentrabajo/{orden.pk}/change/",
                             self.datos_orden(orden, pagos=[(self.efectivo.pk, "1000")]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(orden.monto_adeudado, 0)

    def test_admin_rechaza_ninguno_con_clave(self):
        orden = self.crear_orden()
        datos = self.datos_orden(orden)
        datos["equipos-0-clave_bloqueo"] = "1234"
        r = self.client.post(f"/admin/catalogo/ordentrabajo/{orden.pk}/change/", datos)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "la clave debe quedar vac")

    def datos_cliente(self, principales):
        d = {"nombre": "Nuevo", "notas": "", "email": "", "direccion": "",
             "telefonos-TOTAL_FORMS": str(len(principales)), "telefonos-INITIAL_FORMS": "0",
             "telefonos-MIN_NUM_FORMS": "0", "telefonos-MAX_NUM_FORMS": "1000", "_save": "Guardar"}
        for i, p in enumerate(principales):
            d[f"telefonos-{i}-numero"] = f"35{i}"
            if p:
                d[f"telefonos-{i}-principal"] = "on"
        return d

    def test_admin_un_solo_telefono_principal(self):
        r = self.client.post("/admin/catalogo/cliente/add/", self.datos_cliente([True, True]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Solo un tel")
        r = self.client.post("/admin/catalogo/cliente/add/", self.datos_cliente([True, False]))
        self.assertEqual(r.status_code, 302)

    def test_orden_cerrada_no_se_edita_ni_se_borra_su_venta(self):
        orden = self.crear_orden()
        orden.equipos.update(estado="arreglado")
        self.pagar(orden, "1000")
        venta = cerrar_orden(orden)
        r = self.client.get(f"/admin/catalogo/ordentrabajo/{orden.pk}/change/")
        self.assertNotContains(r, 'name="_save"')
        r = self.client.post(f"/admin/catalogo/ordentrabajo/{orden.pk}/change/", self.datos_orden(orden))
        self.assertEqual(r.status_code, 403)
        e = orden.equipos.first()
        r = self.client.get(f"/admin/catalogo/equiporecibido/{e.pk}/change/")
        self.assertNotContains(r, 'name="_save"')
        self.assertEqual(self.client.get(f"/admin/catalogo/venta/{venta.pk}/delete/").status_code, 403)

    def test_accion_cerrar_orden(self):
        orden = self.crear_orden()
        orden.equipos.update(estado="arreglado")
        r = self.client.post("/admin/catalogo/ordentrabajo/",
                             {"action": "cerrar_ordenes", "_selected_action": [orden.pk]}, follow=True)
        self.assertContains(r, "saldo")
        self.assertFalse(Venta.objects.exists())
        self.pagar(orden, "1000")
        self.client.post("/admin/catalogo/ordentrabajo/",
                         {"action": "cerrar_ordenes", "_selected_action": [orden.pk]}, follow=True)
        self.assertEqual(Venta.objects.count(), 1)

    def test_desplegables_solo_activos(self):
        Marca.objects.create(nombre="Inactiva", activa=False)
        Marca.objects.create(nombre="Activa", activa=True)
        r = self.client.get("/admin/catalogo/producto/add/")
        self.assertContains(r, "Activa")
        self.assertNotContains(r, "Inactiva")
