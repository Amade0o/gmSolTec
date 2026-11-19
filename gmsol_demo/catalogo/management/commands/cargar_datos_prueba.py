from django.core.management.base import BaseCommand

from catalogo.models import (
    CategoriaProducto, CategoriaReparacion, Cliente, Marca, MetodoPago,
    ModeloEquipo, Producto, Reparacion, Telefono,
)


class Command(BaseCommand):
    help = "Carga datos de prueba. Se puede correr varias veces sin duplicar nada."

    def handle(self, *args, **options):
        # Marcas y modelos de equipo
        marcas = {n: Marca.objects.get_or_create(nombre=n)[0]
                  for n in ["Samsung", "Motorola", "Xiaomi", "HP"]}
        modelos = [
            ("Galaxy A14", "Samsung", "celular"),
            ("Galaxy A54", "Samsung", "celular"),
            ("Moto G54", "Motorola", "celular"),
            ("Redmi Note 12", "Xiaomi", "celular"),
            ("Pavilion 15", "HP", "notebook"),
        ]
        for nombre, marca, tipo in modelos:
            ModeloEquipo.objects.get_or_create(
                nombre=nombre, marca=marcas[marca], defaults={"tipo_id": tipo})

        # Categorías y productos
        categorias = {n: CategoriaProducto.objects.get_or_create(nombre=n)[0]
                      for n in ["Cables", "Cargadores", "Vidrios templados", "Fundas", "Otras"]}
        productos = [
            ("Cable USB-C 1m", "Cables", 1000, 2500),
            ("Cargador 20W", "Cargadores", 4000, 9000),
            ("Vidrio templado A14", "Vidrios templados", 800, 3000),
            ("Funda transparente", "Fundas", 600, 2500),
        ]
        for nombre, categoria, compra, venta in productos:
            Producto.objects.get_or_create(
                nombre=nombre,
                defaults={"categoria": categorias[categoria],
                          "precio_compra": compra, "precio_venta": venta})

        # Categorías de reparación y sus variantes
        reparaciones = {
            "Cambio de módulo": ["Módulo OLED", "Módulo original"],
            "Cambio de batería": ["Batería estándar"],
            "Pin de carga": ["Cambio de pin de carga"],
            "Revisión / diagnóstico": ["Revisión / diagnóstico"],
            "Otras": ["Otra reparación"],
        }
        for categoria, variantes in reparaciones.items():
            cat = CategoriaReparacion.objects.get_or_create(nombre=categoria)[0]
            for variante in variantes:
                Reparacion.objects.get_or_create(nombre=variante, categoria=cat)

        # Métodos de pago
        metodos = [
            ("Efectivo", "efectivo", 0),
            ("Transferencia", "digital", 0),
            ("Débito", "digital", 5),
            ("Crédito", "digital", 15),
        ]
        for nombre, cuenta, recargo in metodos:
            MetodoPago.objects.get_or_create(
                nombre=nombre, defaults={"cuenta": cuenta, "recargo_porcentaje": recargo})

        # Clientes con teléfonos (solo si el cliente es nuevo)
        clientes = [
            ("Juan Pérez", [("3584111111", True), ("3584222222", False)]),
            ("María Gómez", [("3584333333", True)]),
        ]
        for nombre, telefonos in clientes:
            cliente, creado = Cliente.objects.get_or_create(nombre=nombre)
            if creado:
                for numero, principal in telefonos:
                    Telefono.objects.create(cliente=cliente, numero=numero, principal=principal)

        self.stdout.write(self.style.SUCCESS("Datos de prueba cargados."))