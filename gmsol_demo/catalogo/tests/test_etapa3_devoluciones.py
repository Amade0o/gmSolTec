from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from catalogo.models import Devolucion, EquipoRecibido, LineaReparacion, OrdenTrabajo
from catalogo.servicios import ReglaDeNegocioError, cerrar_orden
from catalogo.tests.test_etapa3_correcciones import Base

D = Decimal


class DevolucionesTests(Base):
    def orden_no_arreglable(self, sena="400"):
        orden = self.crear_orden()                      # total 1000, un equipo
        orden.equipos.update(estado="no_arreglable")
        if sena:
            self.pagar(orden, sena)
        return orden

    def deber(self, orden, monto):
        return Devolucion.objects.create(orden_trabajo=orden, monto=D(monto))

    def devolver(self, dev, metodo=None):
        dev.metodo_pago = metodo or self.efectivo
        dev.fecha_devolucion = timezone.now()
        dev.save()

    # --- total y estados ---
    def test_lo_que_no_se_arregla_no_se_cobra(self):
        orden = self.crear_orden(D("1000"))
        equipo2 = EquipoRecibido.objects.create(
            orden_trabajo=orden, tipo="celular", problema="x", tipo_bloqueo="ninguno", estado="no_arreglable")
        LineaReparacion.objects.create(equipo=equipo2, reparacion=self.reparacion, precio_vendido=D("600"))
        self.assertEqual(orden.total, D("1000"))        # la línea del equipo no arreglable no cuenta

    def test_no_arreglable_sin_sena_queda_finalizada(self):
        self.assertEqual(self.orden_no_arreglable(sena=None).estado, "finalizada")

    def test_no_arreglable_con_sena_falta_devolver(self):
        orden = self.orden_no_arreglable()
        self.assertEqual(orden.estado, "no_arreglable")
        self.assertEqual(orden.monto_retenido, D("400"))

    def test_hay_que_devolver_sigue_reservado(self):
        orden = self.orden_no_arreglable()
        self.deber(orden, "400")
        self.assertEqual(orden.monto_a_devolver, D("400"))
        self.assertEqual(orden.monto_devuelto, 0)
        self.assertEqual(orden.monto_retenido, D("400"))
        self.assertEqual(orden.estado, "no_arreglable")

    def test_marcar_devuelta_finaliza_la_orden(self):
        orden = self.orden_no_arreglable()
        dev = self.deber(orden, "400")
        self.devolver(dev)
        self.assertTrue(dev.devuelta)
        self.assertEqual(orden.monto_devuelto, D("400"))
        self.assertEqual(orden.monto_a_devolver, 0)
        self.assertEqual(orden.monto_pagado, 0)
        self.assertEqual(orden.monto_retenido, 0)
        self.assertEqual(orden.estado, "finalizada")

    def test_devolucion_parcial_sigue_no_arreglable(self):
        orden = self.orden_no_arreglable("400")
        self.devolver(self.deber(orden, "150"))
        self.assertEqual(orden.monto_retenido, D("250"))
        self.assertEqual(orden.estado, "no_arreglable")

    def test_finalizada_puede_volver_si_se_corrige(self):
        orden = self.orden_no_arreglable(sena=None)
        self.assertEqual(orden.estado, "finalizada")
        orden.equipos.update(estado="pendiente")        # se había marcado mal
        self.assertEqual(orden.estado, "pendiente")

    # --- validaciones ---
    def test_no_devuelve_mas_de_lo_pagado(self):
        orden = self.orden_no_arreglable("400")
        with self.assertRaises(ValidationError):
            Devolucion(orden_trabajo=orden, monto=D("401")).full_clean()
        self.deber(orden, "300")
        with self.assertRaises(ValidationError):
            Devolucion(orden_trabajo=orden, monto=D("101")).full_clean()
        Devolucion(orden_trabajo=orden, monto=D("100")).full_clean()

    def test_editar_una_devolucion_no_se_cuenta_dos_veces(self):
        orden = self.orden_no_arreglable("400")
        dev = self.deber(orden, "400")
        dev.full_clean()

    def test_devuelta_necesita_metodo(self):
        orden = self.orden_no_arreglable()
        dev = Devolucion(orden_trabajo=orden, monto=D("100"), fecha_devolucion=timezone.now())
        with self.assertRaises(ValidationError) as ctx:
            dev.full_clean()
        self.assertIn("metodo_pago", ctx.exception.message_dict)

    def test_monto_cero_invalido(self):
        with self.assertRaises(ValidationError):
            Devolucion(orden_trabajo=self.orden_no_arreglable(), monto=D("0")).full_clean()

    def test_no_se_devuelve_en_una_orden_cerrada(self):
        orden = self.crear_orden()
        orden.equipos.update(estado="arreglado")
        self.pagar(orden, "1000")
        cerrar_orden(orden)
        with self.assertRaises(ValidationError):
            Devolucion(orden_trabajo=orden, monto=D("100")).full_clean()

    # --- orden mixta y cierre ---
    def test_orden_mixta_se_cierra_despues_de_devolver(self):
        orden = self.crear_orden(D("1000"))                         # equipo 1: se arregla, 1000
        equipo2 = EquipoRecibido.objects.create(
            orden_trabajo=orden, tipo="celular", problema="x", tipo_bloqueo="ninguno", estado="no_arreglable")
        LineaReparacion.objects.create(equipo=equipo2, reparacion=self.reparacion, precio_vendido=D("600"))
        orden.equipos.exclude(pk=equipo2.pk).update(estado="arreglado")
        self.pagar(orden, "1600")                                   # la seña cubría los dos equipos
        self.assertEqual(orden.estado, "lista")
        self.assertEqual(orden.monto_adeudado, D("-600"))           # pagó 600 de más
        with self.assertRaises(ReglaDeNegocioError):
            cerrar_orden(orden)
        dev = self.deber(orden, "600")                              # hay que devolver 600
        with self.assertRaises(ReglaDeNegocioError):
            cerrar_orden(orden)                                     # todavía no se devolvió
        self.devolver(dev)
        venta = cerrar_orden(orden)
        self.assertEqual(venta.total, D("1000"))
        self.assertEqual(orden.estado, "cerrada")

    def test_cerrar_orden_no_arreglable_o_finalizada(self):
        con_sena = self.orden_no_arreglable("400")
        with self.assertRaises(ReglaDeNegocioError) as ctx:
            cerrar_orden(con_sena)
        self.assertIn("devolver", str(ctx.exception))
        sin_sena = self.orden_no_arreglable(sena=None)
        with self.assertRaises(ReglaDeNegocioError) as ctx:
            cerrar_orden(sin_sena)
        self.assertIn("terminó sin venta", str(ctx.exception))

    def test_se_puede_volver_a_pagar_despues_de_devolver(self):
        orden = self.crear_orden(D("1000"))
        self.pagar(orden, "1000")
        self.devolver(self.deber(orden, "300"))
        from catalogo.models import Pago
        Pago(orden_trabajo=orden, metodo_pago=self.efectivo, monto=D("300")).full_clean()
        with self.assertRaises(ValidationError):
            Pago(orden_trabajo=orden, metodo_pago=self.efectivo, monto=D("301")).full_clean()


class DevolucionesAdminTests(Base):
    def setUp(self):
        super().setUp()
        from django.contrib.auth import get_user_model
        get_user_model().objects.create_superuser("admin", "a@a.com", "pass")
        self.client.login(username="admin", password="pass")

    def test_pantallas_cargan_y_filtro_de_pendientes(self):
        orden = self.crear_orden()
        orden.equipos.update(estado="no_arreglable")
        self.pagar(orden, "400")
        pendiente = Devolucion.objects.create(orden_trabajo=orden, monto=D("200"))
        hecha = Devolucion.objects.create(
            orden_trabajo=orden, monto=D("100"), metodo_pago=self.efectivo, fecha_devolucion=timezone.now())
        r = self.client.get("/admin/catalogo/ordentrabajo/")
        self.assertEqual(r.status_code, 200)
        r = self.client.get(f"/admin/catalogo/ordentrabajo/{orden.pk}/change/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Devoluciones")
        r = self.client.get("/admin/catalogo/devolucion/?fecha_devolucion__isempty=1")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f"/devolucion/{pendiente.pk}/change/")
        self.assertNotContains(r, f"/devolucion/{hecha.pk}/change/")
        self.assertEqual(self.client.get("/admin/catalogo/devolucion/add/").status_code, 403)
        self.assertEqual(self.client.get(f"/admin/catalogo/devolucion/{pendiente.pk}/change/").status_code, 200)
