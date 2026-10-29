from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.db import IntegrityError, transaction

from catalogo.models import (
    CategoriaProducto, CategoriaReparacion, Cliente, EquipoRecibido,
    LineaProductoOrden, LineaReparacion, MetodoPago, OrdenTrabajo, Pago,
    Producto, Reparacion, Venta,
)

D = Decimal


class BaseConPagos(TestCase):
    """Datos comunes: dos métodos de pago, un cliente y un catálogo mínimo."""

    def setUp(self):
        self.efectivo = MetodoPago.objects.create(
            nombre="Efectivo", cuenta="efectivo", recargo_porcentaje=D("0"))
        self.tarjeta = MetodoPago.objects.create(
            nombre="Tarjeta", cuenta="digital", recargo_porcentaje=D("15"))
        self.cliente = Cliente.objects.create(nombre="Juan")

        cat_rep = CategoriaReparacion.objects.create(nombre="Pantalla")
        self.reparacion = Reparacion.objects.create(nombre="Cambio de módulo", categoria=cat_rep)
        cat_prod = CategoriaProducto.objects.create(nombre="Cables")
        self.producto = Producto.objects.create(
            nombre="Cable USB", categoria=cat_prod,
            precio_compra=D("100"), precio_venta=D("250"))

    def crear_orden(self, precio_reparacion=D("1000"), cantidad_producto=0):
        """Orden con 1 equipo y 1 reparación. Si cantidad_producto > 0, suma el cable a 250 c/u."""
        orden = OrdenTrabajo.objects.create(cliente=self.cliente)
        equipo = EquipoRecibido.objects.create(
            orden_trabajo=orden, tipo="celular", problema="No carga", tipo_bloqueo="ninguno")
        LineaReparacion.objects.create(
            equipo=equipo, reparacion=self.reparacion, precio_vendido=precio_reparacion)
        if cantidad_producto:
            LineaProductoOrden.objects.create(
                orden_trabajo=orden, producto=self.producto,
                cantidad_adquirida=cantidad_producto, precio_vendido=D("250"))
        return orden

    def pagar(self, orden, monto, metodo=None):
        return Pago.objects.create(
            orden_trabajo=orden, metodo_pago=metodo or self.efectivo, monto=D(monto))


class MetodoPagoTests(BaseConPagos):
    def test_recargo_por_defecto_es_cero(self):
        m = MetodoPago.objects.create(nombre="Transferencia", cuenta="digital")
        self.assertEqual(m.recargo_porcentaje, 0)

    def test_recargo_negativo_es_invalido(self):
        m = MetodoPago(nombre="Raro", cuenta="digital", recargo_porcentaje=D("-1"))
        with self.assertRaises(ValidationError):
            m.full_clean()


class PagoCalculosTests(BaseConPagos):
    def test_recargo_y_total_cobrado(self):
        # Producto de $100 con tarjeta 15 %: el cliente paga 115, al negocio entran 100
        pago = self.pagar(self.crear_orden(), "100", self.tarjeta)
        self.assertEqual(pago.recargo_monto, D("15.00"))
        self.assertEqual(pago.total_cobrado, D("115.00"))

    def test_efectivo_sin_recargo(self):
        pago = self.pagar(self.crear_orden(), "100", self.efectivo)
        self.assertEqual(pago.recargo_monto, 0)
        self.assertEqual(pago.total_cobrado, D("100.00"))

    def test_propiedades_con_monto_vacio_no_rompen(self):
        # Pasa en la fila vacía del inline del admin
        pago = Pago()
        self.assertEqual(pago.recargo_monto, 0)
        self.assertEqual(pago.total_cobrado, 0)


class PagoRecargoCopiadoTests(BaseConPagos):
    def test_copia_el_recargo_del_metodo_si_viene_vacio(self):
        pago = self.pagar(self.crear_orden(), "100", self.tarjeta)
        self.assertEqual(pago.recargo_porcentaje, D("15"))

    def test_respeta_un_recargo_explicito(self):
        pago = Pago.objects.create(
            orden_trabajo=self.crear_orden(), metodo_pago=self.tarjeta,
            monto=D("100"), recargo_porcentaje=D("10"))
        self.assertEqual(pago.recargo_porcentaje, D("10"))

    def test_respeta_un_recargo_explicito_de_cero(self):
        # 0 no es "vacío": no debe pisarse con el 15 % de la tarjeta
        pago = Pago.objects.create(
            orden_trabajo=self.crear_orden(), metodo_pago=self.tarjeta,
            monto=D("100"), recargo_porcentaje=D("0"))
        self.assertEqual(pago.recargo_porcentaje, 0)

    def test_cambiar_el_metodo_no_altera_pagos_viejos(self):
        pago = self.pagar(self.crear_orden(), "100", self.tarjeta)
        self.tarjeta.recargo_porcentaje = D("12")
        self.tarjeta.save()
        pago.refresh_from_db()
        self.assertEqual(pago.recargo_porcentaje, D("15"))
        # y un pago nuevo ya usa el 12
        nuevo = self.pagar(self.crear_orden(), "100", self.tarjeta)
        self.assertEqual(nuevo.recargo_porcentaje, D("12"))


class PagoValidacionesTests(BaseConPagos):
    def test_monto_cero_es_invalido(self):
        pago = Pago(metodo_pago=self.efectivo, monto=D("0"))
        with self.assertRaises(ValidationError) as ctx:
            pago.full_clean()
        self.assertIn("monto", ctx.exception.message_dict)

    def test_monto_negativo_es_invalido(self):
        pago = Pago(metodo_pago=self.efectivo, monto=D("-5"))
        with self.assertRaises(ValidationError) as ctx:
            pago.full_clean()
        self.assertIn("monto", ctx.exception.message_dict)

    def test_recargo_negativo_es_invalido(self):
        pago = Pago(metodo_pago=self.efectivo, monto=D("100"), recargo_porcentaje=D("-1"))
        with self.assertRaises(ValidationError) as ctx:
            pago.full_clean()
        self.assertIn("recargo_porcentaje", ctx.exception.message_dict)

    def test_pago_de_venta_directa_es_valido(self):
        venta = Venta.objects.create(total=D("100"))
        pago = Pago(metodo_pago=self.efectivo, monto=D("100"), venta=venta)
        pago.full_clean()
        pago.save()
        self.assertIsNone(pago.orden_trabajo)
        self.assertIn(f"Venta #{venta.id}", str(pago))

    def test_pago_con_orden_y_venta_es_invalido(self):
        venta = Venta.objects.create(total=D("100"))
        pago = Pago(orden_trabajo=self.crear_orden(), venta=venta,
                    metodo_pago=self.efectivo, monto=D("100"))
        with self.assertRaises(ValidationError):
            pago.full_clean()
    
    def test_pago_sin_dueno_no_se_puede_guardar(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Pago.objects.create(metodo_pago=self.efectivo, monto=D("100"))


class OrdenMontosTests(BaseConPagos):
    def test_total_suma_reparaciones_y_productos(self):
        orden = self.crear_orden(precio_reparacion=D("1000"), cantidad_producto=2)
        self.assertEqual(orden.total, D("1500"))   # 1000 + 2 × 250

    def test_total_sin_lineas_es_cero(self):
        orden = OrdenTrabajo.objects.create(cliente=self.cliente)
        self.assertEqual(orden.total, 0)

    def test_monto_pagado_no_incluye_el_recargo(self):
        orden = self.crear_orden()
        self.pagar(orden, "100", self.tarjeta)         # el cliente paga 115
        self.assertEqual(orden.monto_pagado, D("100"))  # a la orden le suman 100

    def test_sena_en_efectivo_y_saldo_con_tarjeta(self):
        orden = self.crear_orden(precio_reparacion=D("1000"))
        self.pagar(orden, "400", self.efectivo)
        self.pagar(orden, "600", self.tarjeta)
        self.assertEqual(orden.monto_pagado, D("1000"))
        self.assertEqual(orden.monto_adeudado, 0)
        recargos = [p.recargo_monto for p in orden.pagos.order_by("id")]
        self.assertEqual(recargos, [D("0"), D("90")])   # el recargo solo cae en la tarjeta

    def test_monto_adeudado_con_sena(self):
        orden = self.crear_orden(precio_reparacion=D("1000"))
        self.pagar(orden, "400")
        self.assertEqual(orden.monto_adeudado, D("600"))


class OrdenAdeudaTests(BaseConPagos):
    def test_adeuda_sin_pagos(self):
        self.assertTrue(self.crear_orden().adeuda)

    def test_adeuda_con_sena(self):
        orden = self.crear_orden()
        self.pagar(orden, "400")
        self.assertTrue(orden.adeuda)

    def test_no_adeuda_si_pago_todo(self):
        orden = self.crear_orden()
        self.pagar(orden, "1000")
        self.assertFalse(orden.adeuda)

    def test_no_adeuda_si_pago_de_mas(self):
        orden = self.crear_orden()
        self.pagar(orden, "1200")
        self.assertLess(orden.monto_adeudado, 0)
        self.assertFalse(orden.adeuda)

    def test_orden_sin_lineas_no_adeuda(self):
        orden = OrdenTrabajo.objects.create(cliente=self.cliente)
        self.assertFalse(orden.adeuda)

class OrdenCerradaTests(BaseConPagos):
    def cerrar(self, orden):
        return Venta.objects.create(
            orden_trabajo=orden, cliente=orden.cliente, total=orden.total)

    def test_orden_nueva_no_esta_cerrada(self):
        orden = self.crear_orden()
        self.assertFalse(orden.cerrada)
        self.assertEqual(orden.estado, "pendiente")

    def test_estado_lista_antes_de_cerrar(self):
        orden = self.crear_orden()
        orden.equipos.update(estado="arreglado")
        self.assertEqual(orden.estado, "lista")

    def test_orden_con_venta_esta_cerrada(self):
        orden = self.crear_orden()
        self.cerrar(orden)
        self.assertTrue(orden.cerrada)
        self.assertEqual(orden.estado, "cerrada")


class DineroRetenidoTests(BaseConPagos):
    def cerrar(self, orden):
        return Venta.objects.create(
            orden_trabajo=orden, cliente=orden.cliente, total=orden.total)

    def test_pago_de_orden_abierta_esta_retenido(self):
        pago = self.pagar(self.crear_orden(), "400")
        self.assertTrue(pago.retenido)

    def test_pago_se_libera_al_cerrar_la_orden(self):
        orden = self.crear_orden()
        pago = self.pagar(orden, "1000")
        self.cerrar(orden)
        pago.refresh_from_db()
        self.assertFalse(pago.retenido)

    def test_pago_de_venta_directa_nunca_esta_retenido(self):
        venta = Venta.objects.create(total=D("100"))
        pago = Pago.objects.create(venta=venta, metodo_pago=self.efectivo, monto=D("100"))
        self.assertFalse(pago.retenido)

    def test_monto_retenido_mientras_esta_abierta(self):
        orden = self.crear_orden()
        self.pagar(orden, "400")
        self.assertEqual(orden.monto_retenido, D("400"))

    def test_monto_retenido_es_cero_al_cerrar(self):
        orden = self.crear_orden()
        self.pagar(orden, "1000")
        self.cerrar(orden)
        orden.refresh_from_db()
        self.assertEqual(orden.monto_retenido, 0)