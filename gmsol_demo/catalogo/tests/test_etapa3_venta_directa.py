from decimal import Decimal

from django.core.exceptions import ValidationError

from catalogo.models import LineaProductoVenta, Pago, Venta
from catalogo.servicios import ReglaDeNegocioError, vender_directo
from catalogo.tests.test_etapa3_correcciones import Base

D = Decimal


class VenderDirectoTests(Base):
    def linea(self, cantidad=2, precio=None):
        return LineaProductoVenta(producto=self.producto, cantidad_adquirida=cantidad, precio_vendido=precio)

    def pago(self, monto, metodo=None):
        return Pago(metodo_pago=metodo or self.efectivo, monto=D(monto))

    def test_venta_simple(self):
        venta = vender_directo([self.linea(2)], [self.pago("500")])
        self.assertEqual(venta.total, D("500"))             # 2 x 250 (precio del producto)
        self.assertIsNone(venta.orden_trabajo)
        self.assertIsNone(venta.cliente)
        self.assertEqual(venta.lineas_producto.get().precio_vendido, D("250"))
        self.assertEqual(venta.pagos.get().monto, D("500"))
        self.assertFalse(venta.pagos.get().retenido)

    def test_precio_cambiado_y_cliente(self):
        venta = vender_directo([self.linea(2, D("200"))], [self.pago("400")], cliente=self.cliente)
        self.assertEqual(venta.total, D("400"))
        self.assertEqual(venta.cliente, self.cliente)

    def test_pago_en_dos_metodos_con_recargo(self):
        venta = vender_directo([self.linea(2)], [self.pago("300"), self.pago("200", self.tarjeta)])
        pagos = list(venta.pagos.order_by("id"))
        self.assertEqual([p.recargo_porcentaje for p in pagos], [D("0"), D("15")])
        self.assertEqual(pagos[1].total_cobrado, D("230"))   # el recargo no cuenta para el total

    def test_sin_productos(self):
        with self.assertRaises(ReglaDeNegocioError):
            vender_directo([], [])

    def test_pagos_distintos_al_total(self):
        for monto in ("499", "501"):
            with self.assertRaises(ReglaDeNegocioError):
                vender_directo([self.linea(2)], [self.pago(monto)])
        with self.assertRaises(ReglaDeNegocioError):
            vender_directo([self.linea(2)], [])
        self.assertFalse(Venta.objects.exists())

    def test_producto_repetido(self):
        with self.assertRaises(ReglaDeNegocioError):
            vender_directo([self.linea(1), self.linea(1)], [self.pago("500")])

    def test_cantidad_cero_no_guarda_nada(self):
        with self.assertRaises(ValidationError):
            vender_directo([self.linea(0)], [])
        self.assertFalse(Venta.objects.exists())

    def test_si_un_pago_falla_no_queda_nada(self):
        with self.assertRaises(ValidationError):
            vender_directo([self.linea(2)], [self.pago("600"), self.pago("-100")])
        self.assertFalse(Venta.objects.exists())
        self.assertFalse(Pago.objects.exists())
        self.assertFalse(LineaProductoVenta.objects.exists())