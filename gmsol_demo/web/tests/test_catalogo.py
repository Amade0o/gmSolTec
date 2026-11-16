"""Pantalla del Catálogo (categorías, marcas, modelos, reparaciones, métodos de pago)."""
from django.urls import reverse

from catalogo.models import CategoriaReparacion, Marca, MetodoPago, ModeloEquipo, Reparacion
from web.views_catalogo import SECCIONES
from web.tests.test_pantallas import Base


class CatalogoTests(Base):
    def test_piden_login(self):
        self.client.logout()
        for url in (reverse("web:catalogo_inicio"), reverse("web:catalogo", args=["marcas"]),
                    reverse("web:catalogo_editar", args=["marcas", self.modelo.marca_id])):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_todas_las_pestanas_cargan(self):
        for clave in SECCIONES:
            with self.subTest(seccion=clave):
                self.assertEqual(self.client.get(reverse("web:catalogo", args=[clave])).status_code, 200)
        self.assertEqual(self.client.get("/catalogo/no-existe/").status_code, 404)

    def test_agregar_marca_y_modelo(self):
        url = reverse("web:catalogo", args=["marcas"])
        r = self.client.post(url, {"nuevo-nombre": "Motorola"})
        self.assertRedirects(r, url)
        moto = Marca.objects.get(nombre="Motorola")
        self.client.post(reverse("web:catalogo", args=["modelos"]),
                         {"nuevo-marca": moto.id, "nuevo-nombre": "G54", "nuevo-tipo": "celular"})
        self.assertTrue(ModeloEquipo.objects.filter(marca=moto, nombre="G54").exists())

    def test_nombre_repetido_no_guarda(self):
        r = self.client.post(reverse("web:catalogo", args=["marcas"]), {"nuevo-nombre": "Samsung"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Marca.objects.filter(nombre="Samsung").count(), 1)

    def test_desactivar_oculta_de_la_lista_y_de_los_desplegables(self):
        url = reverse("web:catalogo_editar", args=["reparaciones", self.reparacion.id])
        self.client.post(url, {"accion": "desactivar"}, follow=True)     # follow: consume el aviso
        self.assertFalse(Reparacion.objects.get(pk=self.reparacion.id).activo)
        r = self.client.get(reverse("web:catalogo", args=["reparaciones"]))
        self.assertNotContains(r, "Módulo OLED")
        r = self.client.get(reverse("web:catalogo", args=["reparaciones"]) + "?estado=todos")
        self.assertContains(r, "Módulo OLED")
        r = self.client.get(reverse("web:orden_nueva"))
        self.assertNotContains(r, "Módulo OLED")
        self.client.post(url, {"accion": "activar"})
        self.assertTrue(Reparacion.objects.get(pk=self.reparacion.id).activo)

    def test_editar_modelo_con_marca_desactivada(self):
        Marca.objects.filter(pk=self.modelo.marca_id).update(activa=False)
        url = reverse("web:catalogo_editar", args=["modelos", self.modelo.id])
        r = self.client.post(url, {"marca": self.modelo.marca_id, "nombre": "Galaxy A15", "tipo": "celular"})
        self.assertRedirects(r, reverse("web:catalogo", args=["modelos"]))
        self.assertEqual(ModeloEquipo.objects.get(pk=self.modelo.id).nombre, "Galaxy A15")

    def test_repetido_se_controla_aunque_la_marca_no_cambie(self):
        ModeloEquipo.objects.create(nombre="Galaxy A15", marca=self.modelo.marca, tipo="celular")
        url = reverse("web:catalogo_editar", args=["modelos", self.modelo.id])
        r = self.client.post(url, {"marca": self.modelo.marca_id, "nombre": "Galaxy A15", "tipo": "celular"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ModeloEquipo.objects.get(pk=self.modelo.id).nombre, "Galaxy A14")

    def test_no_se_elige_una_categoria_desactivada(self):
        apagada = CategoriaReparacion.objects.create(nombre="Vieja", activo=False)
        r = self.client.post(reverse("web:catalogo", args=["reparaciones"]),
                             {"nuevo-categoria": apagada.id, "nuevo-nombre": "Cambio de pin"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Reparacion.objects.filter(nombre="Cambio de pin").exists())

    def test_metodo_de_pago_con_recargo(self):
        self.client.post(reverse("web:catalogo", args=["metodos-pago"]),
                         {"nuevo-nombre": "Crédito", "nuevo-cuenta": "digital", "nuevo-recargo_porcentaje": "10"})
        self.assertEqual(MetodoPago.objects.get(nombre="Crédito").recargo_porcentaje, 10)
        r = self.client.get(reverse("web:catalogo", args=["metodos-pago"]))
        self.assertContains(r, "10 %")
