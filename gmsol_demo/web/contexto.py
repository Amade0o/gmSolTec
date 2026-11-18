"""Datos que usan todas las pantallas (registrado en settings.TEMPLATES).

menu: los grupos del menú lateral, con cuál está activo según la pantalla.
"""

# (sección, dirección, texto, ícono, pantallas que la marcan como activa)
_TRABAJO = [
    ("inicio", "web:inicio", "Inicio", "i-inicio", {"inicio"}),
    ("ordenes", "web:ordenes", "Órdenes de trabajo", "i-ordenes", {"ordenes", "orden_detalle", "orden_nueva", "orden_entregar"}),
    ("ventas", "web:ventas", "Registro de ventas", "i-ventas", {"ventas", "venta_detalle", "venta_rapida"}),
    ("devoluciones", "web:devoluciones", "Devoluciones", "i-devol", {"devoluciones"}),
]
_REGISTROS = [
    ("clientes", "web:clientes", "Clientes", "i-clientes", {"clientes", "cliente_detalle", "cliente_nuevo"}),
    ("productos", "web:productos", "Productos", "i-productos", {"productos", "producto_detalle", "producto_nuevo"}),
]
# "Configuración" (antes "Catálogo"): las listas que se eligen al cargar (tipos de equipo, marcas,
# modelos, reparaciones, categorías, métodos de pago). Las direcciones siguen siendo /catalogo/.
_AJUSTES = [
    ("catalogo", "web:catalogo_inicio", "Configuración", "i-catalogo", {"catalogo", "catalogo_inicio", "catalogo_editar"}),
]
PROXIMAMENTE = [
    ("Caja", "i-caja"), ("Compras y proveedores", "i-compras"),
    ("Estadísticas", "i-stats"), ("Facturación ARCA", "i-arca"),
]


def _items(lista, pantalla):
    return [{
        "url": url, "texto": texto, "icono": icono,
        "activo": pantalla in pantallas,
        # "page" en la pantalla principal de la sección, "true" en sus subpantallas
        "actual": "page" if pantalla == url.split(":")[1] else "true",
    } for _, url, texto, icono, pantallas in lista]


def menu(request):
    match = getattr(request, "resolver_match", None)
    pantalla = match.url_name if match and match.namespace == "web" else None
    return {"menu": [
        ("Trabajo", _items(_TRABAJO, pantalla)),
        ("Registros", _items(_REGISTROS, pantalla)),
        ("Ajustes", _items(_AJUSTES, pantalla)),
    ], "proximamente": PROXIMAMENTE}
