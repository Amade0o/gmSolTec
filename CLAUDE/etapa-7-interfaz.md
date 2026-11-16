# GMSol — Etapa 7: interfaz propia (diseño técnico v1)

> **Uso:** documento corto para cargar como contexto. Complementa a `guia-de-diseno-gmsol.md` (cómo se ve) y a `GMSol-stack-y-arquitectura.md` (stack).
> **Estado:** pasos **7.0 a 7.7 hechos** (16/11/2026): login, Inicio, lista de órdenes, nueva orden, detalle, entregar, venta rápida, devoluciones, ventas, clientes y productos, con el diseño **v2** ("H2 + pista de progreso", ver `guia-de-diseno-gmsol.md`). Falta: pantallas de caja y stock (etapa 4) y del catálogo.
> **Leyenda:** ✅ decidido · 💡 propuesta (falta confirmar)

---

## 1. Qué se construye

La interfaz que va a usar el dueño todos los días, en la PC del local y, de a ratos, en el celular. Reemplaza al admin de Django para el trabajo diario. **El admin queda para las altas del catálogo** (marcas, modelos, productos, reparaciones, métodos de pago) hasta que se hagan esas pantallas.

---

## 2. Decisiones técnicas

| # | Decisión | Detalle |
|---|---|---|
| 1 | ✅ **App nueva `web`** | Vistas, plantillas y archivos estáticos. `catalogo` sigue siendo solo modelos, servicios y admin |
| 2 | ✅ **Las vistas no tienen reglas de negocio** | Llaman a funciones de `catalogo/servicios.py` (`cerrar_orden`, `vender_directo` y las nuevas). Así las reglas están en un solo lugar |
| 3 | ✅ **CSS propio** | Sin Bootstrap ni Tailwind. Los valores de la guía van como variables CSS: `gmsol.css` (base v1) + `gmsol-v2.css` (diseño v2, se carga encima; sacándolo se vuelve a la v1) |
| 4 | ✅ **HTMX para lo dinámico** | El resumen de la orden (total, saldo) se recalcula **en el servidor** al cambiar un campo, con la misma lógica de recargos y totales del sistema. Evita duplicar reglas en JavaScript |
| 5 | ✅ **JavaScript propio solo para el patrón de bloqueo** | La grilla de 9 puntos que guarda `1-5-9-6` (`static/web/js/patron.js`). Sin JS la clave se escribe a mano |
| 6 | ✅ **HTMX en un archivo local** | Se descarga una vez a `static/`, sin depender de internet para funcionar |
| 7 | ✅ **Tipografía por enlace a Google Fonts al principio** | Figtree, Barlow Condensed e IBM Plex Mono. En la etapa 12 (instalación) se pasan a archivos locales |
| 10 | ✅ **Pista de progreso** | El estado de la orden se dibuja como pista de circuito (Recibida → Revisión → Lista → Entregada). Se calcula con el filtro `pista` de `formato.py`; no hay datos nuevos |
| 8 | ✅ **Login simple de Django**, un solo usuario | |
| 9 | ✅ **Todas las pantallas requieren login** | |
| 11 | ✅ **Nueva orden carga un equipo** | Si el cliente deja más de uno, se agregan desde el detalle ("Agregar otro equipo"). Evita formularios anidados |
| 12 | ✅ **Después de guardar se redirige** | Así F5 no guarda dos veces. Los mensajes (éxito o error) se muestran arriba del contenido |
| 13 | ✅ **Venta rápida: un pago con monto vacío se lleva lo que falta** | Para la venta más común (un producto, un pago) no hay que escribir el total |

---

## 3. Estructura de carpetas

```
gmsol_demo/
├── catalogo/               modelos, servicios, admin, tests (ya existe)
└── web/                    app nueva
    ├── urls.py
    ├── views.py            (se puede dividir en un paquete cuando crezca)
    ├── forms.py
    ├── tests/
    ├── templates/web/
    │   ├── base.html           franja superior + menú lateral
    │   ├── inicio.html
    │   ├── ordenes/            lista, nueva, detalle
    │   └── parciales/          trozos que HTMX actualiza (resumen, filas)
    └── static/web/
        ├── css/gmsol.css       base (v1)
        ├── css/gmsol-v2.css    diseño v2, se carga encima
        ├── js/htmx.min.js
        ├── js/patron.js
        └── img/                logo.png, logo-oscuro.png
```

---

## 4. Mapa de pantallas

| Dirección | Pantalla | Se apoya en |
|---|---|---|
| `/` | Inicio: resumen con conteos y órdenes en curso | `OrdenTrabajo.estado` y `monto_a_devolver` |
| `/ordenes/` | Lista de órdenes: búsqueda y filtros por estado | |
| `/ordenes/nueva/` | **Nueva orden** (pantalla aprobada) | `crear_orden` (nueva) |
| `/ordenes/<n>/` | Detalle: estado de cada equipo, agregar/quitar reparaciones y productos, agregar equipo, pagos, registrar devolución | Servicios nuevos |
| `/ordenes/<n>/entregar/` | Cobrar el saldo y entregar (crea la Venta) | `entregar_orden` |
| `/devoluciones/` | Marcar que el dinero ya se devolvió; avisa órdenes con saldo a favor sin devolución registrada | `marcar_devuelta` |
| `/ventas/rapida/` | Venta rápida | `vender_directo` |
| `/ventas/` | Ventas: filtro por período (hoy, 7 días, este mes, todas), búsqueda por cliente o `#n`, total del período | `Venta.total` |
| `/ventas/<n>/` | Detalle de la venta. Si cerró una orden, muestra sus equipos, productos y pagos | |
| `/clientes/` | Clientes: búsqueda por nombre, teléfono o email; cantidad de órdenes y la última | |
| `/clientes/nuevo/` | Alta de cliente ("Guardar y crear orden" abre Nueva orden con el cliente elegido) | `crear_cliente` |
| `/productos/` | Productos: activos / desactivados / todos, por categoría, búsqueda por nombre o marca; margen calculado | `Producto.margen` |
| `/productos/nuevo/`, `/productos/<n>/` | Alta y edición, margen en vivo (HTMX), activar/desactivar, últimas ventas | |
| `/clientes/<n>/` | Ficha: datos editables, teléfonos (principal), órdenes, compras directas y saldo en órdenes abiertas | `agregar_telefono`, `marcar_telefono_principal`, `quitar_telefono` |
| `/entregar/` | Entregar un equipo: buscar la orden, cobrar el saldo, cerrar | `cerrar_orden` |
| `/login/`, `/logout/` | Acceso | Login de Django |
| `/admin/` | Altas del catálogo | Admin de Django |

---

## 5. Servicios nuevos que van a hacer falta (en `catalogo/servicios.py`)

| Función | Para qué |
|---|---|
| `crear_orden(cliente, equipo, lineas_reparacion, lineas_producto, pagos)` | Crear la orden completa en una sola transacción, con las mismas validaciones que el admin |
| `agregar_equipo`, `agregar_reparacion`, `quitar_reparacion`, `agregar_producto`, `quitar_producto` | Editar una orden abierta (una orden cerrada no se toca) |
| `entregar_orden(orden, metodo, recargo)` | Cobra el saldo y cierra con `cerrar_orden`, todo o nada |
| `agregar_pago(orden, metodo, monto)` | Registrar un pago de una orden abierta |
| `cambiar_estado_equipo(equipo, estado)` | Marcar arreglado, sin falla o no arreglable |
| `registrar_devolucion(orden, monto o reparacion)` y `marcar_devuelta(devolucion, metodo)` | Los dos pasos de la devolución |
| `crear_cliente`, `agregar_telefono`, `marcar_telefono_principal`, `quitar_telefono` | Regla: si el cliente tiene teléfonos, uno solo es principal (el primero lo es solo; al quitar el principal pasa al más antiguo) |

---

## 6. Orden de trabajo (cada paso es una rama de avance con tests)

| Paso | Qué se hace |
|---|---|
| **7.0** ✅ | App `web`, plantilla base (franja y menú), `gmsol.css` con las variables de la guía, login, logo e **Inicio**. Rediseño v2 (`gmsol-v2.css`, fecha del día, pista de progreso) |
| **7.1** ✅ | Lista de órdenes: filtros por estado, búsqueda por cliente o teléfono, `#12` abre la orden |
| **7.2** ✅ | **Nueva orden** (el servicio `crear_orden`, el formulario, el resumen con HTMX y el patrón de bloqueo) |
| **7.3** ✅ | Detalle de orden: estados, reparaciones, productos, pagos, registrar devoluciones |
| **7.4** ✅ | Venta rápida |
| **7.5** ✅ | Entregar + pantalla de Devoluciones |
| **7.6** ✅ | Ventas (lista y detalle) y Clientes (lista, alta y ficha) |
| **7.7** ✅ | Productos (lista, alta, edición, margen en vivo) |
| Después | Pantallas de caja y stock (junto con la etapa 4), y las del catálogo si hace falta |

Cada paso lleva tests con el cliente de pruebas de Django (la pantalla carga, pide login, y las acciones hacen lo que dicen).

---

## 7. Celular

Una sola plantilla para todo. Por debajo de 860 px el menú pasa a una barra horizontal y los paneles se apilan. Se prueba en el navegador achicando la ventana.

---

## 8. Pendientes

| # | Tema |
|---|---|
| 1 | Confirmar las decisiones 💡 de la sección 2 |
| 2 | Tipografía en archivos locales (etapa 12) |
| 3 | Búsqueda de cliente dentro de "Nueva orden": hoy es un desplegable con nombre y teléfono. Con muchos clientes conviene un buscador |
| 4 | "Guardar e imprimir" (etapa 10) |
| 5 | La tarjeta "Devoluciones por hacer" cuenta solo devoluciones **registradas**; una orden con saldo a favor sin devolución registrada no suma. Decidir si debe contar también esas |
| 6 | Columna "días en el taller" con aviso de 30 días (se probó en la propuesta K). Falta definir si los 30 días cuentan desde que se deja el equipo o desde que se avisa que está listo |
| 8 | Corregir un pago mal cargado: hoy solo desde el admin |
| 9 | "Catálogo" del menú sigue yendo al admin (categorías, marcas, modelos, reparaciones, métodos de pago) |
| 11 | Productos: un producto con categoría o marca desactivada se puede seguir editando sin cambiarlas (el formulario no las vuelve a controlar); elegir una desactivada no se permite |
| 10 | Ventas: no hay forma de anular una venta mal hecha (hoy solo desde el admin) |
| 7 | Texto del saldo: la guía dice "A favor del cliente: $X (se debe devolver)"; la pantalla muestra "A favor: $ X (devolver)". Unificar |
