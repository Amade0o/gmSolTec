"""Servicios que usan las pantallas propias (etapa 7)."""
from decimal import Decimal

from django.core.exceptions import ValidationError

from catalogo.models import (
    Devolucion, EquipoRecibido, LineaProductoOrden, LineaReparacion, OrdenTrabajo, Pago,
)
from catalogo.servicios import (
    ReglaDeNegocioError, agregar_equipo, agregar_pago, agregar_producto, agregar_reparacion,
    cambiar_estado_equipo, crear_orden, entregar_orden, marcar_devuelta, quitar_producto,
    quitar_reparacion, registrar_devolucion, devolver_reparacion, monto_para_devolver,
)
from catalogo.tests.test_etapa3_correcciones import Base

D = Decimal


class CrearOrdenTests(Base):
    def equipo(self, **datos):
        return EquipoRecibido(tipo_id="celular", problema="No carga", **datos)

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
        equipo = agregar_equipo(orden, EquipoRecibido(tipo_id="pc", problema="No prende"),
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


class DevolverReparacionTests(Base):
    """Devolver una reparación puntual desde Devoluciones (pedido del 17/11/2026)."""

    def orden_dos_reparaciones(self, pagado):
        orden = self.crear_orden(D("15000"))                       # batería
        equipo = orden.equipos.get()
        pantalla = agregar_reparacion(equipo, LineaReparacion(reparacion=self.reparacion, precio_vendido=D("40000")))
        bateria = equipo.lineas_reparacion.exclude(pk=pantalla.pk).get()
        if pagado:
            self.pagar(orden, pagado)
        return orden, bateria, pantalla

    def test_pago_todo_devuelve_la_reparacion_entera(self):
        orden, bateria, _ = self.orden_dos_reparaciones("55000")
        self.assertEqual(monto_para_devolver(bateria), D("15000"))
        dev = devolver_reparacion(bateria, self.efectivo)
        self.assertTrue(dev.devuelta)
        self.assertEqual(orden.total, D("40000"))                  # la batería ya no se cobra
        self.assertEqual(orden.monto_adeudado, D("0"))             # pagó 55.000, le devolvieron 15.000
        self.assertEqual(orden.equipos.get().lineas_reparacion.count(), 2)   # sigue a la vista

    def test_pago_una_parte_devuelve_solo_lo_de_mas(self):
        orden, bateria, _ = self.orden_dos_reparaciones("45000")
        self.assertEqual(monto_para_devolver(bateria), D("5000"))  # 45.000 pagados − 40.000 que quedan
        dev = devolver_reparacion(bateria)                         # sin método: queda pendiente
        self.assertFalse(dev.devuelta)
        self.assertEqual(orden.monto_a_devolver, D("5000"))

    def test_si_no_pago_de_mas_no_hay_nada_para_devolver(self):
        orden, bateria, _ = self.orden_dos_reparaciones("10000")
        with self.assertRaises(ReglaDeNegocioError):
            devolver_reparacion(bateria, self.efectivo)
        self.assertFalse(Devolucion.objects.exists())

    def test_no_se_devuelve_dos_veces_ni_se_quita(self):
        orden, bateria, _ = self.orden_dos_reparaciones("55000")
        devolver_reparacion(bateria, self.efectivo)
        with self.assertRaises(ReglaDeNegocioError):
            devolver_reparacion(bateria, self.efectivo)
        with self.assertRaises(ReglaDeNegocioError):
            quitar_reparacion(bateria)

    def test_despues_de_devolver_se_puede_entregar(self):
        orden, bateria, _ = self.orden_dos_reparaciones("55000")
        devolver_reparacion(bateria, self.efectivo)
        cambiar_estado_equipo(orden.equipos.get(), "arreglado")
        venta = entregar_orden(orden)
        self.assertEqual(venta.total, D("40000"))


class BorrarTests(Base):
    """Borrar lo cargado por error, con las mismas reglas que el admin (pedido del 18/11/2026)."""

    def test_quitar_pago(self):
        from catalogo.servicios import quitar_pago
        orden = self.crear_orden()
        pago = self.pagar(orden, "400")
        quitar_pago(pago)
        self.assertEqual(orden.monto_pagado, D("0"))

    def test_no_se_quita_un_pago_que_ya_se_devolvio(self):
        from catalogo.servicios import quitar_pago
        orden = self.crear_orden()
        pago = self.pagar(orden, "400")
        registrar_devolucion(orden, monto=D("400"))
        with self.assertRaises(ReglaDeNegocioError):
            quitar_pago(pago)

    def test_anular_devolucion_pendiente_y_no_la_hecha(self):
        from catalogo.servicios import anular_devolucion
        orden = self.crear_orden()
        self.pagar(orden, "400")
        pendiente = registrar_devolucion(orden, monto=D("100"))
        anular_devolucion(pendiente)
        hecha = marcar_devuelta(registrar_devolucion(orden, monto=D("100")), self.efectivo)
        with self.assertRaises(ReglaDeNegocioError):
            anular_devolucion(hecha)

    def test_quitar_equipo_deja_al_menos_uno(self):
        from catalogo.servicios import quitar_equipo
        orden = self.crear_orden()
        with self.assertRaises(ReglaDeNegocioError):
            quitar_equipo(orden.equipos.get())
        otro = agregar_equipo(orden, EquipoRecibido(tipo_id="pc", problema="x"),
                              [LineaReparacion(reparacion=self.reparacion, precio_vendido=D("1"))])
        quitar_equipo(otro)
        self.assertEqual(orden.equipos.count(), 1)

    def test_eliminar_orden_solo_sin_plata(self):
        from catalogo.servicios import eliminar_orden
        orden = self.crear_orden()
        pago = self.pagar(orden, "100")
        with self.assertRaises(ReglaDeNegocioError):
            eliminar_orden(orden)
        pago.delete()
        eliminar_orden(orden)
        self.assertFalse(OrdenTrabajo.objects.exists())

    def test_anular_venta_directa_y_no_la_de_una_orden(self):
        from catalogo.servicios import anular_venta_directa, vender_directo
        from catalogo.models import LineaProductoVenta, Venta
        venta = vender_directo([LineaProductoVenta(producto=self.producto, cantidad_adquirida=1)],
                               [Pago(metodo_pago=self.efectivo, monto=self.producto.precio_venta)])
        anular_venta_directa(venta)
        self.assertFalse(Venta.objects.exists())
        orden = self.crear_orden()
        cambiar_estado_equipo(orden.equipos.get(), "arreglado")
        de_orden = entregar_orden(orden, self.efectivo)
        with self.assertRaises(ReglaDeNegocioError):
            anular_venta_directa(de_orden)

    def test_eliminar_cliente_solo_sin_historial(self):
        from catalogo.servicios import eliminar_cliente
        from catalogo.models import Cliente
        self.crear_orden()
        with self.assertRaises(ReglaDeNegocioError):
            eliminar_cliente(self.cliente)
        nuevo = Cliente.objects.create(nombre="Sin nada")
        eliminar_cliente(nuevo)

    def test_devolver_saldo_a_favor(self):
        from catalogo.servicios import devolver_saldo_a_favor
        orden = self.crear_orden(D("1000"))
        self.pagar(orden, "1500")                                   # pagó 500 de más
        registrar_devolucion(orden, monto=D("200"))                 # 200 ya registrados, pendientes
        devuelto = devolver_saldo_a_favor(orden, self.efectivo)
        self.assertEqual(devuelto, D("500"))
        orden = OrdenTrabajo.objects.get(pk=orden.pk)
        self.assertEqual(orden.monto_adeudado, D("0"))
        self.assertEqual(orden.monto_a_devolver, D("0"))
        with self.assertRaises(ReglaDeNegocioError):
            devolver_saldo_a_favor(orden, self.efectivo)


class NoArreglableConProductosTests(Base):
    """Regla del 18/11/2026: si ningún equipo tuvo arreglo pero se lleva productos, la orden se
    cobra y se entrega con una venta de esos productos (antes quedaba trabada en "no arreglable")."""

    def test_se_entrega_con_venta_de_los_productos(self):
        orden = self.crear_orden(D("30000"), cant_producto=2)      # 30.000 + 2 × 250
        self.pagar(orden, "30500")
        cambiar_estado_equipo(orden.equipos.get(), "no_arreglable")
        self.assertEqual(orden.total, D("500"))
        self.assertEqual(orden.estado, "lista")
        self.assertEqual(orden.monto_adeudado, D("-30000"))         # hay que devolver la reparación
        marcar_devuelta(registrar_devolucion(orden, monto=D("30000")), self.efectivo)
        venta = entregar_orden(orden)
        self.assertEqual(venta.total, D("500"))
