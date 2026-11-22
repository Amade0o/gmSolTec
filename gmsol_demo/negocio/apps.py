from django.apps import AppConfig


class NegocioConfig(AppConfig):
    """La app con todo lo del negocio: catálogo, clientes, órdenes, pagos y ventas
    (y, desde la etapa 4, caja y stock). Antes se llamaba 'catalogo'.

    Las pantallas están en la app 'web'; acá están los datos (models/) y las reglas (servicios/)."""
    name = "negocio"
    verbose_name = "Negocio"
