"""Servicios que usan las pantallas propias (etapa 7)."""
from decimal import Decimal

from django.core.exceptions import ValidationError

from catalogo.models import (
    Devolucion, EquipoRecibido, LineaProductoOrden, LineaReparacion, OrdenTrabajo, Pago,
)
from catalogo.servicios import (
    ReglaDeNegocioError, agregar_equipo, agregar_pago, agregar_producto, agregar_reparacion,
    cambiar_estado_equipo, crear_orden, entregar_orden, marcar_devuelta, quitar_producto,
    quitar_reparacion, registrar_devolucion,
)
from catalogo.tests.test_etapa3_correcciones import Base

D = Decimal


class CrearOrdenTests(Base):
    def equipo(self, **datos):
        return EquipoRecibido(tipo="celular", problema="No carga", **datos)

    def linea(self, precio="1000"):
        return LineaReparacion(reparacion=self.reparacion, precio_vendido=D(precio))

    def test_crea_todo_junto(self):
        orden = crear_orden(
            self.cliente, self.equipo(), [self.linea("1000")],
            lineas_producto=[LineaProductoOrden(producto=self.producto, cantidad_adquirida=2)],
            pagos=[Pago(metodo_pago=self.efectivo, monto=D("500"))])
        self.assertEqual(orden.equipos.count(), 1)
        self.assertEqual(orden.total, D("1500"))          # 1000 + 2 x 250
        self.assertEqual(orden.monto_pagado, D("500"))
        self.assertEqual(orden.estado, "pendiente")

    def test_sin_reparacion_no_guarda_nada(self):
        with self.assertRaises(ReglaDeNegocioError):
            crear_orden(self.cliente, self.equipo(), [])
        self.assertEqual(OrdenTrabajo.objects.count(), 0)

    def test_sena_mayor_al_total_no_guarda_nada(self):
        with self.assertRaises(ValidationError):
            crear_orden(self.cliente, self.equipo(), [self.linea("1000")],
                        pagos=[Pago(metodo_pago=self.efectivo, monto=D("1001"))])
        self.assertEqual(OrdenTrabajo.objects.count(), 0)
        self.assertEqual(Pago.objects.count(), 0)

    def test_equipo_nuevo_no_puede_venir_arreglado(self):
        with self.assertRaises(ValidationError):
            crear_orden(self.cliente, self.equipo(estado="arreglado"), [self.linea()])
        self.assertEqual(OrdenTrabajo.objects.count(), 0)

    def test_bloqueo_ninguno_sin_clave(self):
        with self.assertRaises(ValidationError):
            crear_orden(self.cliente, self.equipo(tipo_bloqueo="ninguno", clave_bloqueo="1234"), [self.linea()])

    def test_producto_repetido(self):
        lineas = [LineaProductoOrden(producto=self.producto, cantidad_adquirida=1),
                  LineaProductoOrden(producto=self.producto, cantidad_adquirida=1)]
        with self.assertRaises(ReglaDeNegocioError):
            crear_orden(self.cliente, self.equipo(), [self.linea()], lineas_producto=lineas)
        self.assertEqual(OrdenTrabajo.objects.count(), 0)


class EditarOrdenTests(Base):
    def test_agregar_equipo_y_reparacion(self):
        orden = self.crear_orden()
        equipo = agregar_equipo(orden, EquipoRecibido(tipo="pc", problema="No prende"),
                                [LineaReparacion(reparacion=self.reparacion, precio_vendido=D("500"))])
        agregar_reparacion(equipo, LineaReparacion(reparacion=self.reparacion, precio_vendido=D("200")))
        self.assertEqual(orden.total, D("1700"))

    def test_quitar_la_ultima_reparacion_no(self):
        orden = self.crear_orden()
        with self.assertRaises(ReglaDeNegocioError):
            quitar_reparacion(LineaReparacion.objects.get(equipo__orden_trabajo=orden))

    def test_quitar_producto(self):
        orden = self.crear_orden(cant_producto=1)
        quitar_producto(orden.lineas_producto.get())
        self.assertEqual(orden.total, D("1000"))

    def test_agregar_producto_copia_el_precio(self):
        orden = self.crear_orden()
        linea = agregar_producto(orden, LineaProductoOrden(producto=self.producto, cantidad_adquirida=1))
        self.assertEqual(linea.precio_vendido, D("250"))

    def test_pago_no_supera_lo_que_falta(self):
        orden = self.crear_orden()
        agregar_pago(orden, self.efectivo, D("600"))
        with self.assertRaises(ValidationError):
            agregar_pago(orden, self.efectivo, D("401"))
        pago = agregar_pago(orden, self.tarjeta, D("400"))
        self.assertEqual(pago.recargo_porcentaje, D("15"))     # copiado del método

    def test_cambiar_estado(self):
        orden = self.crear_orden()
        cambiar_estado_equipo(orden.equipos.get(), "arreglado")
        self.assertEqual(orden.estado, "lista")
        with self.assertRaises(ReglaDeNegocioError):
            cambiar_estado_equipo(orden.equipos.get(), "inventado")

    def test_orden_cerrada_no_se_toca(self):
        orden = self.crear_orden()
        cambiar_estado_equipo(orden.equipos.get(), "arreglado")
        entregar_orden(orden, self.efectivo)
        with self.assertRaises(ReglaDeNegocioError):
            agregar_pago(orden, self.efectivo, D("1"))
        with self.assertRaises(ReglaDeNegocioError):
            cambiar_estado_equipo(orden.equipos.get(), "pendiente")
        with self.assertRaises(ReglaDeNegocioError):
            agregar_producto(orden, LineaProductoOrden(producto=self.producto, cantidad_adquirida=1))


class DevolucionYEntregaTests(Base):
    def test_dos_pasos(self):
        orden = self.crear_orden()
        self.pagar(orden, "400")
        cambiar_estado_equipo(orden.equipos.get(), "no_arreglable")
        dev = registrar_devolucion(orden, linea_reparacion=LineaReparacion.objects.get(equipo__orden_trabajo=orden),
                                   monto=D("400"))
        self.assertFalse(dev.devuelta)
        self.assertEqual(orden.estado, "no_arreglable")
        marcar_devuelta(dev, self.efectivo)
        self.assertTrue(Devolucion.objects.get(pk=dev.pk).devuelta)
        self.assertEqual(orden.estado, "finalizada")
        with self.assertRaises(ReglaDeNegocioError):
            marcar_devuelta(dev, self.efectivo)

    def test_entregar_cobra_el_saldo_y_cierra(self):
        orden = self.crear_orden()
        self.pagar(orden, "300")
        cambiar_estado_equipo(orden.equipos.get(), "arreglado")
        venta = entregar_orden(orden, self.tarjeta)
        self.assertEqual(venta.total, D("1000"))
        self.assertEqual(orden.pagos.count(), 2)
        self.assertEqual(orden.estado, "cerrada")

    def test_entregar_sin_metodo_si_debe(self):
        orden = self.crear_orden()
        cambiar_estado_equipo(orden.equipos.get(), "arreglado")
        with self.assertRaises(ReglaDeNegocioError):
            entregar_orden(orden)

    def test_entregar_pendiente_no_cobra_nada(self):
        orden = self.crear_orden()
        with self.assertRaises(ReglaDeNegocioError):
            entregar_orden(orden, self.efectivo)
        self.assertEqual(orden.pagos.count(), 0)            # el pago se deshizo
