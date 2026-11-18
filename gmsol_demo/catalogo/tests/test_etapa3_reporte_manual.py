import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from catalogo.models import (
    Devolucion, EquipoRecibido, LineaProductoOrden, LineaReparacion, OrdenTrabajo, Pago,
)
from catalogo.servicios import cerrar_orden
from catalogo.tests.test_etapa3_correcciones import Base

D = Decimal


class ModeloReporteTests(Base):
    def orden_mixta(self):
        """Equipo 1 (1000, se arregla) y equipo 2 (600, no se arregla). Seña 1600."""
        orden = self.crear_orden(D("1000"))
        eq1 = orden.equipos.first()
        eq2 = EquipoRecibido.objects.create(orden_trabajo=orden, tipo_id="celular", problema="x")
        linea2 = LineaReparacion.objects.create(equipo=eq2, reparacion=self.reparacion, precio_vendido=D("600"))
        pago = self.pagar(orden, "1600")
        eq1.estado, eq2.estado = "arreglado", "no_arreglable"
        eq1.save(); eq2.save()
        return orden, eq2, linea2, pago

    # --- el bug grave: un pago ya guardado no se vuelve a controlar ---
    def test_pago_existente_sigue_valido_cuando_baja_el_total(self):
        orden, _, _, pago = self.orden_mixta()
        self.assertEqual(orden.total, D("1000"))
        pago.full_clean()                       # antes fallaba: "supera lo que falta pagar"

    def test_pago_nuevo_igual_se_controla(self):
        orden, _, _, _ = self.orden_mixta()
        with self.assertRaises(ValidationError):
            Pago(orden_trabajo=orden, metodo_pago=self.efectivo, monto=D("1")).full_clean()

    def test_pago_existente_con_monto_cambiado_se_controla(self):
        orden = self.crear_orden(D("1000"))
        pago = self.pagar(orden, "400")
        pago.monto = D("1001")
        with self.assertRaises(ValidationError):
            pago.full_clean()
        pago.monto = D("1000")
        pago.full_clean()

    # --- equipos ---
    def test_equipo_nuevo_empieza_en_revision(self):
        orden = OrdenTrabajo.objects.create(cliente=self.cliente)
        for estado in ("arreglado", "sin_falla", "no_arreglable"):
            e = EquipoRecibido(orden_trabajo=orden, tipo_id="celular", problema="x", estado=estado)
            with self.assertRaises(ValidationError) as ctx:
                e.full_clean()
            self.assertIn("estado", ctx.exception.message_dict)
        EquipoRecibido(orden_trabajo=orden, tipo_id="celular", problema="x").full_clean()

    def test_equipo_guardado_puede_cambiar_de_estado(self):
        orden = self.crear_orden()
        e = orden.equipos.first()
        e.estado = "arreglado"
        e.full_clean()

    def test_bloqueo_por_defecto_es_ninguno(self):
        orden = OrdenTrabajo.objects.create(cliente=self.cliente)
        self.assertEqual(EquipoRecibido(orden_trabajo=orden, tipo_id="celular", problema="x").tipo_bloqueo, "ninguno")

    def test_etiqueta_del_estado_pendiente(self):
        e = self.crear_orden().equipos.first()
        self.assertEqual(e.get_estado_display(), "En revisión / reparación")

    # --- devolver una reparación completa ---
    def test_devolver_reparacion_completa_carga_el_monto(self):
        orden, _, linea2, _ = self.orden_mixta()
        d = Devolucion(orden_trabajo=orden, linea_reparacion=linea2)
        d.full_clean()
        d.save()
        self.assertEqual(d.monto, D("600"))
        self.assertEqual(orden.monto_a_devolver, D("600"))

    def test_devolver_reparacion_de_equipo_que_se_arregla(self):
        # Regla cambiada el 17/11/2026 (pedido del dueño): una reparación que se cancela también
        # se puede devolver. Sigue en la orden, pero deja de sumar al total. Una sola vez.
        orden, _, _, _ = self.orden_mixta()
        linea1 = LineaReparacion.objects.get(equipo=orden.equipos.first())
        d = Devolucion(orden_trabajo=orden, linea_reparacion=linea1)
        d.full_clean()
        d.save()
        self.assertEqual(d.monto, D("1000"))
        self.assertEqual(orden.total, D("0"))
        self.assertTrue(LineaReparacion.objects.filter(pk=linea1.pk).exists())     # no se borra
        with self.assertRaises(ValidationError) as ctx:
            Devolucion(orden_trabajo=orden, linea_reparacion=linea1, monto=D("1")).full_clean()
        self.assertIn("linea_reparacion", ctx.exception.message_dict)

    def test_devolver_reparacion_de_otra_orden_no_se_puede(self):
        orden, _, _, _ = self.orden_mixta()
        otra, _, linea_otra, _ = self.orden_mixta()
        with self.assertRaises(ValidationError):
            Devolucion(orden_trabajo=orden, linea_reparacion=linea_otra).full_clean()

    def test_devolucion_sin_monto_ni_reparacion(self):
        orden = self.crear_orden()
        self.pagar(orden, "100")
        with self.assertRaises(ValidationError):
            Devolucion(orden_trabajo=orden).full_clean()

    def test_monto_manual_tambien_sirve(self):
        orden, _, _, _ = self.orden_mixta()
        d = Devolucion(orden_trabajo=orden, monto=D("250"))
        d.full_clean()

    # --- elegir el método = ya se devolvió ---
    def test_elegir_metodo_completa_la_fecha(self):
        orden, _, linea2, _ = self.orden_mixta()
        d = Devolucion.objects.create(orden_trabajo=orden, linea_reparacion=linea2)
        self.assertFalse(d.devuelta)
        d.metodo_pago = self.efectivo
        d.save()
        self.assertTrue(d.devuelta)
        self.assertIsNotNone(d.fecha_devolucion)

    def test_flujo_completo_orden_mixta(self):
        orden, _, linea2, _ = self.orden_mixta()
        self.assertEqual(orden.monto_adeudado, D("-600"))
        d = Devolucion.objects.create(orden_trabajo=orden, linea_reparacion=linea2)
        d.metodo_pago = self.efectivo
        d.save()
        venta = cerrar_orden(orden)
        self.assertEqual(venta.total, D("1000"))


class AdminReporteTests(Base):
    def setUp(self):
        super().setUp()
        get_user_model().objects.create_superuser("admin", "a@a.com", "pass")
        self.client.login(username="admin", password="pass")

    def datos_orden(self, orden, devoluciones=(), equipos_estado=None, pagos_existentes=True):
        """Formulario completo de una orden ya guardada (equipos, pagos existentes, devoluciones nuevas)."""
        d = {"cliente": self.cliente.pk, "_save": "Guardar",
             "lineas_producto-TOTAL_FORMS": "0", "lineas_producto-INITIAL_FORMS": "0",
             "lineas_producto-MIN_NUM_FORMS": "0", "lineas_producto-MAX_NUM_FORMS": "1000"}
        equipos = list(orden.equipos.order_by("id"))
        d.update({"equipos-TOTAL_FORMS": str(len(equipos)), "equipos-INITIAL_FORMS": str(len(equipos)),
                  "equipos-MIN_NUM_FORMS": "0", "equipos-MAX_NUM_FORMS": "1000"})
        for i, e in enumerate(equipos):
            d.update({f"equipos-{i}-id": e.pk, f"equipos-{i}-orden_trabajo": orden.pk, f"equipos-{i}-tipo": e.tipo_id,
                      f"equipos-{i}-problema": e.problema, f"equipos-{i}-tipo_bloqueo": e.tipo_bloqueo,
                      f"equipos-{i}-clave_bloqueo": "", f"equipos-{i}-accesorios_dejados": "",
                      f"equipos-{i}-estado": (equipos_estado or {}).get(e.pk, e.estado)})
        pagos = list(orden.pagos.order_by("id")) if pagos_existentes else []
        d.update({"pagos-TOTAL_FORMS": str(len(pagos)), "pagos-INITIAL_FORMS": str(len(pagos)),
                  "pagos-MIN_NUM_FORMS": "0", "pagos-MAX_NUM_FORMS": "1000"})
        for i, p in enumerate(pagos):
            d.update({f"pagos-{i}-id": p.pk, f"pagos-{i}-orden_trabajo": orden.pk,
                      f"pagos-{i}-metodo_pago": p.metodo_pago_id, f"pagos-{i}-monto": str(p.monto),
                      f"pagos-{i}-recargo_porcentaje": str(p.recargo_porcentaje)})
        existentes = list(orden.devoluciones.order_by("id"))
        d.update({"devoluciones-TOTAL_FORMS": str(len(existentes) + len(devoluciones)),
                  "devoluciones-INITIAL_FORMS": str(len(existentes)),
                  "devoluciones-MIN_NUM_FORMS": "0", "devoluciones-MAX_NUM_FORMS": "1000"})
        for i, x in enumerate(existentes):
            d.update({f"devoluciones-{i}-id": x.pk, f"devoluciones-{i}-orden_trabajo": orden.pk,
                      f"devoluciones-{i}-monto": str(x.monto), f"devoluciones-{i}-nota": x.nota,
                      f"devoluciones-{i}-linea_reparacion": x.linea_reparacion_id or ""})
        for j, (linea, monto) in enumerate(devoluciones):
            i = len(existentes) + j
            d.update({f"devoluciones-{i}-linea_reparacion": linea or "", f"devoluciones-{i}-monto": monto or "",
                      f"devoluciones-{i}-nota": ""})
        return d

    def orden_mixta(self):
        orden = self.crear_orden(D("1000"))
        eq2 = EquipoRecibido.objects.create(orden_trabajo=orden, tipo_id="celular", problema="x")
        linea2 = LineaReparacion.objects.create(equipo=eq2, reparacion=self.reparacion, precio_vendido=D("600"))
        self.pagar(orden, "1600")
        return orden, eq2, linea2

    def url(self, orden):
        return f"/admin/catalogo/ordentrabajo/{orden.pk}/change/"

    # --- T6 / T7: el flujo que se trababa ---
    def test_T6_marcar_no_arreglable_y_registrar_devolucion_desde_la_orden(self):
        orden, eq2, linea2 = self.orden_mixta()
        eq1 = orden.equipos.exclude(pk=eq2.pk).get()
        # 1) marcar los estados (el total baja a 1000 y el pago de 1600 queda "de más")
        r = self.client.post(self.url(orden), self.datos_orden(orden, equipos_estado={eq1.pk: "arreglado", eq2.pk: "no_arreglable"}))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(orden.estado, "lista")
        self.assertEqual(orden.monto_adeudado, D("-600"))
        # 2) registrar la devolución eligiendo la reparación: ANTES daba "el pago supera lo que falta pagar"
        r = self.client.post(self.url(orden), self.datos_orden(orden, devoluciones=[(linea2.pk, "")]))
        self.assertEqual(r.status_code, 302, r.context["errors"] if r.status_code == 200 else "")
        d = Devolucion.objects.get()
        self.assertEqual(d.monto, D("600"))
        self.assertFalse(d.devuelta)
        self.assertEqual(orden.monto_a_devolver, D("600"))

    def test_T7_guardar_la_orden_con_un_pago_viejo_ya_no_se_traba(self):
        orden = self.crear_orden(D("3000"))
        self.pagar(orden, "5000")                     # seña antes del precio (se cargó con total 0)
        orden.equipos.update(estado="arreglado")
        r = self.client.post(self.url(orden), self.datos_orden(orden, devoluciones=[(None, "2000")]))
        self.assertEqual(r.status_code, 302, r.context["errors"] if r.status_code == 200 else "")
        self.assertEqual(orden.monto_a_devolver, D("2000"))

    def test_marcar_devuelta_desde_el_menu_devoluciones(self):
        orden, eq2, linea2 = self.orden_mixta()
        orden.equipos.exclude(pk=eq2.pk).update(estado="arreglado")
        eq2.estado = "no_arreglable"; eq2.save()
        d = Devolucion.objects.create(orden_trabajo=orden, linea_reparacion=linea2)
        r = self.client.get(f"/admin/catalogo/devolucion/{d.pk}/change/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f"Orden #{orden.id}")           # el título muestra la orden
        r = self.client.post(f"/admin/catalogo/devolucion/{d.pk}/change/",
                             {"nota": "", "metodo_pago": self.efectivo.pk, "_save": "Guardar"})
        self.assertEqual(r.status_code, 302, r.context["errors"] if r.status_code == 200 else "")
        d.refresh_from_db()
        self.assertTrue(d.devuelta)
        cerrar_orden(orden)                                    # ahora sí se puede cerrar

    def test_la_orden_solo_registra_no_marca_como_devuelta(self):
        orden, eq2, linea2 = self.orden_mixta()
        r = self.client.get(self.url(orden))
        self.assertContains(r, "Devoluciones")
        self.assertNotContains(r, "Fecha devolucion")          # esos campos están solo en el menú Devoluciones
        self.assertNotContains(r, 'name="devoluciones-0-metodo_pago"')

    def test_el_filtro_muestra_pendientes_y_devueltas(self):
        orden, eq2, linea2 = self.orden_mixta()
        pend = Devolucion.objects.create(orden_trabajo=orden, monto=D("100"))
        hecha = Devolucion.objects.create(orden_trabajo=orden, monto=D("200"), metodo_pago=self.efectivo)
        r = self.client.get("/admin/catalogo/devolucion/?estado=pendiente")
        self.assertContains(r, f"/devolucion/{pend.pk}/change/")
        self.assertNotContains(r, f"/devolucion/{hecha.pk}/change/")
        r = self.client.get("/admin/catalogo/devolucion/?estado=devuelta")
        self.assertContains(r, f"/devolucion/{hecha.pk}/change/")
        self.assertNotContains(r, f"/devolucion/{pend.pk}/change/")

    def test_la_reparacion_a_devolver_se_elige_solo_entre_las_de_esta_orden(self):
        orden, eq2, linea2 = self.orden_mixta()
        otra, _, linea_otra = self.orden_mixta()
        r = self.client.get(self.url(orden))
        html = r.content.decode()
        self.assertIn(f'value="{linea2.pk}"', html)
        self.assertNotIn(f'value="{linea_otra.pk}"', html)

    # --- visibilidad de la orden y vuelta al menú ---
    def test_titulos_con_el_numero_de_orden(self):
        orden = self.crear_orden()
        equipo = orden.equipos.first()
        r = self.client.get(self.url(orden))
        self.assertContains(r, f"Orden #{orden.id} · Juan")
        r = self.client.get(f"/admin/catalogo/equiporecibido/{equipo.pk}/change/")
        self.assertContains(r, f"Orden #{orden.id} · Juan · Equipo #{equipo.pk}")

    def test_guardar_un_equipo_vuelve_al_menu_de_ordenes(self):
        orden = self.crear_orden()
        equipo = orden.equipos.first()
        linea = equipo.lineas_reparacion.first()
        datos = {"orden_trabajo": orden.pk, "tipo": "celular", "problema": "x", "tipo_bloqueo": "ninguno",
                 "clave_bloqueo": "", "accesorios_dejados": "", "estado": "pendiente",
                 "lineas_reparacion-TOTAL_FORMS": "1", "lineas_reparacion-INITIAL_FORMS": "1",
                 "lineas_reparacion-MIN_NUM_FORMS": "0", "lineas_reparacion-MAX_NUM_FORMS": "1000",
                 "lineas_reparacion-0-id": linea.pk, "lineas_reparacion-0-equipo": equipo.pk,
                 "lineas_reparacion-0-reparacion": self.reparacion.pk, "lineas_reparacion-0-precio_vendido": "1000",
                 "lineas_reparacion-0-nota": "", "_save": "Guardar"}
        r = self.client.post(f"/admin/catalogo/equiporecibido/{equipo.pk}/change/", datos)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/admin/catalogo/ordentrabajo/")

    # --- el saldo se entiende ---
    def test_saldo_claro_en_la_lista_y_en_la_orden(self):
        debe = self.crear_orden(D("1000")); self.pagar(debe, "400")
        a_favor = self.crear_orden(D("1000")); self.pagar(a_favor, "1000")
        a_favor.equipos.update(estado="no_arreglable")          # total 0, pagado 1000
        saldada = self.crear_orden(D("1000")); self.pagar(saldada, "1000")
        r = self.client.get("/admin/catalogo/ordentrabajo/")
        self.assertContains(r, "Debe $600.00")
        self.assertContains(r, "A favor del cliente: $1000.00 (se debe devolver)")
        self.assertContains(r, "Saldado")
        r = self.client.get(self.url(a_favor))
        self.assertContains(r, "A favor del cliente: $1000.00")

    # --- equipo nuevo desde el admin ---
    def test_admin_rechaza_equipo_nuevo_con_resultado(self):
        d = {"cliente": self.cliente.pk, "_save": "Guardar",
             "equipos-TOTAL_FORMS": "1", "equipos-INITIAL_FORMS": "0", "equipos-MIN_NUM_FORMS": "0", "equipos-MAX_NUM_FORMS": "1000",
             "equipos-0-tipo": "celular", "equipos-0-problema": "x", "equipos-0-tipo_bloqueo": "ninguno",
             "equipos-0-clave_bloqueo": "", "equipos-0-accesorios_dejados": "", "equipos-0-estado": "no_arreglable",
             "lineas_producto-TOTAL_FORMS": "0", "lineas_producto-INITIAL_FORMS": "0", "lineas_producto-MIN_NUM_FORMS": "0", "lineas_producto-MAX_NUM_FORMS": "1000",
             "pagos-TOTAL_FORMS": "0", "pagos-INITIAL_FORMS": "0", "pagos-MIN_NUM_FORMS": "0", "pagos-MAX_NUM_FORMS": "1000",
             "devoluciones-TOTAL_FORMS": "0", "devoluciones-INITIAL_FORMS": "0", "devoluciones-MIN_NUM_FORMS": "0", "devoluciones-MAX_NUM_FORMS": "1000"}
        r = self.client.post("/admin/catalogo/ordentrabajo/add/", d)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "siempre empieza en revisión")
        d["equipos-0-estado"] = "pendiente"
        self.assertEqual(self.client.post("/admin/catalogo/ordentrabajo/add/", d).status_code, 302)

    def test_el_formulario_de_orden_trae_ninguno_por_defecto(self):
        r = self.client.get("/admin/catalogo/ordentrabajo/add/")
        self.assertRegex(r.content.decode(), r'<option value="ninguno" selected>')

    # --- el orden de las columnas: primero qué, después el precio ---
    def test_primero_el_producto_o_la_reparacion_y_despues_el_precio(self):
        orden = self.crear_orden()
        html = self.client.get(self.url(orden)).content.decode()
        bloque = html[html.index("lineas_producto-group"):]
        cabeceras = re.findall(r"<th[^>]*>\s*([A-Za-zÁ-ú ]+?)\s*(?:<span|</th>)", bloque[:3000])
        self.assertLess(cabeceras.index("Producto"), cabeceras.index("Cantidad adquirida"))
        self.assertLess(cabeceras.index("Cantidad adquirida"), cabeceras.index("Precio vendido"))
        equipo = orden.equipos.first()
        html = self.client.get(f"/admin/catalogo/equiporecibido/{equipo.pk}/change/").content.decode()
        bloque = html[html.index("lineas_reparacion-group"):]
        cabeceras = re.findall(r"<th[^>]*>\s*([A-Za-zÁ-ú ]+?)\s*(?:<span|</th>)", bloque[:3000])
        self.assertLess(cabeceras.index("Reparacion"), cabeceras.index("Precio vendido"))
