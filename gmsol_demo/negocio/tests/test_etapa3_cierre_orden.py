from decimal import Decimal

from negocio.models import Venta
from negocio.servicios import ReglaDeNegocioError, cerrar_orden
from negocio.tests.test_etapa3_pagos import BaseConPagos

D = Decimal


class CerrarOrdenTests(BaseConPagos):
    def orden_lista_y_paga(self):
        orden = self.crear_orden()                 # total 1000
        orden.equipos.update(estado="arreglado")
        self.pagar(orden, "1000")
        return orden

    def test_cierra_una_orden_lista_y_paga(self):
        orden = self.orden_lista_y_paga()
        venta = cerrar_orden(orden)
        self.assertEqual(venta.total, D("1000"))
        self.assertEqual(venta.cliente, self.cliente)
        self.assertEqual(venta.orden_trabajo, orden)
        self.assertTrue(orden.cerrada)

    def test_no_cierra_con_equipos_pendientes(self):
        orden = self.crear_orden()
        self.pagar(orden, "1000")
        with self.assertRaises(ReglaDeNegocioError):
            cerrar_orden(orden)
        self.assertFalse(Venta.objects.exists())

    def test_no_cierra_si_adeuda(self):
        orden = self.crear_orden()
        orden.equipos.update(estado="arreglado")
        self.pagar(orden, "400")
        with self.assertRaises(ReglaDeNegocioError):
            cerrar_orden(orden)
        self.assertFalse(Venta.objects.exists())

    def test_no_cierra_una_orden_no_arreglable(self):
        orden = self.crear_orden()
        orden.equipos.update(estado="no_arreglable")
        self.pagar(orden, "1000")
        with self.assertRaises(ReglaDeNegocioError):
            cerrar_orden(orden)

    def test_no_cierra_dos_veces(self):
        orden = self.orden_lista_y_paga()
        cerrar_orden(orden)
        with self.assertRaises(ReglaDeNegocioError):
            cerrar_orden(orden)
        self.assertEqual(Venta.objects.count(), 1)