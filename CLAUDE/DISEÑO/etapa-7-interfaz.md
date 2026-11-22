# GMSol — Etapa 7: interfaz propia (diseño técnico v1)

> **Uso:** documento corto para cargar como contexto. Complementa a [guia-de-diseno-gmsol.md](../BPMN%20Y%20MODELO/guia-de-diseno-gmsol.md) (cómo se ve), [stack_tecnologico.md](stack_tecnologico.md) (stack), el [diagrama de clases v6](../MODULOS/diagrama-clases-modulos-1-a-3-v6.md) y el [plan](../MODULOS/0_Plan.md).
> **Estado:** pasos **7.0 a 7.8 hechos** (16/11/2026): login, Inicio, lista de órdenes, nueva orden, detalle, entregar, venta rápida, devoluciones, ventas, clientes, productos y catálogo, con el diseño **v2** ("H2 + pista de progreso", ver la [guía de diseño](../BPMN%20Y%20MODELO/guia-de-diseno-gmsol.md)). Falta: pantallas de caja y stock (etapa 4).
> **Leyenda:** ✅ decidido · 💡 propuesta (falta confirmar)

---

## 1. Qué se construye

La interfaz que va a usar el dueño todos los días, en la PC del local y, de a ratos, en el celular. Reemplaza al admin de Django para el trabajo diario. El admin queda solo para corregir cosas puntuales (ej.: un pago mal cargado).

---

## 2. Decisiones técnicas

| # | Decisión | Detalle |
|---|---|---|
| 1 | ✅ **App nueva `web`** | Vistas, plantillas y archivos estáticos. `negocio` (antes `catalogo`, renombrada el 21/11/2026) tiene solo modelos, servicios y admin |
| 2 | ✅ **Las vistas no tienen reglas de negocio** | Llaman a funciones de `negocio/servicios/` (`cerrar_orden`, `vender_directo` y las nuevas). Así las reglas están en un solo lugar |
| 3 | ✅ **CSS propio** | Sin Bootstrap ni Tailwind. Los valores de la guía van como variables CSS: un solo `gmsol.css` en capas (`@layer`), con tamaños en `rem` (ver la sección 8 de la [guía de diseño](../BPMN%20Y%20MODELO/guia-de-diseno-gmsol.md)) |
| 4 | ✅ **HTMX para lo dinámico** | El resumen de la orden (total, saldo) se recalcula **en el servidor** al cambiar un campo, con la misma lógica de recargos y totales del sistema. Evita duplicar reglas en JavaScript |
| 5 | ✅ **JavaScript propio solo para el patrón de bloqueo** | La grilla de 9 puntos que guarda `1-5-9-6` (`static/web/js/patron.js`). Sin JS la clave se escribe a mano |
| 6 | ✅ **HTMX en un archivo local** | Se descarga una vez a `static/`, sin depender de internet para funcionar |
| 7 | ✅ **Tipografía en archivos locales** | Figtree, Barlow Condensed e IBM Plex Mono, en `static/web/fuentes/` (`@font-face` en `gmsol.css`). Funciona sin internet |
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
├── negocio/                modelos, servicios, admin, tests (antes se llamaba catalogo/)
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
        ├── css/gmsol.css       todos los estilos (diseño v2), en capas
        ├── fuentes/            Figtree, Barlow Condensed, IBM Plex Mono (woff2)
        ├── js/htmx.min.js
        ├── js/app.js           avisos, confirmar, imprimir, buscador de clientes
        ├── js/patron.js
        └── img/                logo.webp, favicon.png, iconos.svg (+ logo.png original)
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
| `/ventas/` | Ventas: filtro por período (hoy, 7 días, este mes, todas), búsqueda por cliente o número (igual que en órdenes), total del período | `Venta.total` |
| `/ventas/<n>/` | Detalle de la venta. Si cerró una orden, muestra sus equipos, productos y pagos | |
| `/clientes/` | Clientes: búsqueda por nombre, teléfono o email; cantidad de órdenes y la última | |
| `/clientes/nuevo/` | Alta de cliente ("Guardar y crear orden" abre Nueva orden con el cliente elegido) | `crear_cliente` |
| `/productos/` | Productos: activos / desactivados / todos, por categoría, búsqueda por nombre o marca; margen calculado | `Producto.margen` |
| `/productos/nuevo/`, `/productos/<n>/` | Alta y edición, margen en vivo (HTMX), activar/desactivar, últimas ventas | |
| `/clientes/<n>/` | Ficha: datos editables, teléfonos (principal), órdenes, compras directas y saldo en órdenes abiertas | `agregar_telefono`, `marcar_telefono_principal`, `quitar_telefono` |
| `/entregar/` | Entregar un equipo: buscar la orden, cobrar el saldo, cerrar | `cerrar_orden` |
| `/login/`, `/logout/` | Acceso | Login de Django |
| `/catalogo/<tabla>/` | Catálogo: una pestaña por tabla (categorías de producto, marcas, modelos, categorías de reparación, reparaciones, métodos de pago). Agregar, buscar, editar, activar/desactivar | `web/views_catalogo.py` |
| `/admin/` | Correcciones puntuales | Admin de Django |

---

## 5. Servicios de la etapa 7 (hoy en `negocio/servicios/`)

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
| **7.0** ✅ | App `web`, plantilla base (franja y menú), `gmsol.css` con las variables de la guía, login, logo e **Inicio**. Rediseño v2 (fecha del día, pista de progreso; hoy todo está en `gmsol.css`) |
| **7.1** ✅ | Lista de órdenes: filtros por estado, búsqueda por cliente o teléfono (el teléfono se compara solo con los dígitos), `#12` abre la orden. `12` sin numeral también la abre si ningún cliente tiene un teléfono que coincida; si coincide alguno, muestra la lista con la orden #12 primera (18/11/2026) |
| **7.2** ✅ | **Nueva orden** (el servicio `crear_orden`, el formulario, el resumen con HTMX y el patrón de bloqueo) |
| **7.3** ✅ | Detalle de orden: estados, reparaciones, productos, pagos, registrar devoluciones |
| **7.4** ✅ | Venta rápida |
| **7.5** ✅ | Entregar + pantalla de Devoluciones |
| **7.6** ✅ | Ventas (lista y detalle) y Clientes (lista, alta y ficha) |
| **7.7** ✅ | Productos (lista, alta, edición, margen en vivo) |
| **7.8** ✅ | Catálogo (una pantalla con pestañas, configurada en `SECCIONES`) |
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
| 2 | ~~Tipografía en archivos locales~~ ✅ ya están en `static/web/fuentes/` |
| 3 | ~~Búsqueda de cliente dentro de "Nueva orden"~~ ✅ la lista se filtra al escribir y carga de a 40 (17/11) |
| 4 | "Guardar e imprimir" (etapa 10) |
| 5 | La tarjeta "Devoluciones por hacer" cuenta solo devoluciones **registradas**; una orden con saldo a favor sin devolución registrada no suma. Decidir si debe contar también esas |
| 6 | Columna "días en el taller" con aviso de 30 días (se probó en la propuesta K). Falta definir si los 30 días cuentan desde que se deja el equipo o desde que se avisa que está listo |
| 8 | Corregir un pago mal cargado: se puede **quitar** en una orden abierta (`quitar_pago`, 18/11); editarlo o tocarlo en una orden cerrada sigue siendo desde el admin |
| 11 | Productos, modelos y reparaciones con una categoría o marca desactivada se pueden seguir editando sin cambiarla (`ConDesactivablesForm`); elegir una desactivada no se permite |
| 12 | Nueva orden busca la reparación "Revisión / diagnóstico" por nombre. Si se renombra o desactiva en el Catálogo, la primera fila viene vacía |
| 10 | Ventas: la venta rápida se puede anular (`anular_venta_directa`, 18/11); la venta que cerró una orden, solo desde el admin |
| 7 | Texto del saldo: la guía dice "A favor del cliente: $X (se debe devolver)"; la pantalla muestra "A favor: $ X (devolver)". Unificar |


---

## Cambios del 17/11/2026 (pedidos del dueño)

- **Cliente de la orden:** "De la lista" **o** "Cliente nuevo" (campo `modo`; lo del otro modo se ignora). La lista muestra **todos** los clientes de la A a la Z, se filtra al escribir y llega de a 40 (el resto se pide solo al bajar). Al cargar uno nuevo avisa si ya existe uno con ese teléfono o nombre ("Usar este").
- **"+ Nuevo" al lado de los desplegables del catálogo** (modelo, reparación, categoría, marca): diálogo con HTMX, sin salir de la pantalla (`views_catalogo.alta_rapida`). Modelo y reparación aceptan una marca/categoría nueva escrita. Si ya existe con ese nombre, se elige esa.
- **Eliminar** en catálogo y productos: solo si nunca se usó; si se usó, se ofrece desactivar.
- **Listas de filas:** una sola fila; "+ Agregar otra" y "Quitar" (app.js). Cantidad vacía = 1; una fila sin producto se ignora.
- **Precio de lista, lo que falta pagar y recargo del método** se muestran con un lápiz para cambiarlos (vacío = automático, misma cuenta que el servidor).
- **Saldo "Sin precio todavía"** en órdenes abiertas sin nada cobrable ni pagado (antes decía "Saldado").
- **Devolver una reparación** desde Devoluciones (o el botón "Devolver" de la orden): ver la regla en [diagrama-clases-modulos-1-a-3-v6.md](../MODULOS/diagrama-clases-modulos-1-a-3-v6.md) §4.5.
- **"Agregar reparación"** destacado dentro de cada equipo.
- Las plantillas no usan `{# #}` de varias líneas (se imprime como texto): hay un test que lo controla.


## Cambios del 18/11/2026 (pedidos del dueño)

- **Estado de la orden** (debajo del Resumen): cómo quedó cada equipo con botones claros ("Ya está arreglado", "No tenía falla", "No tiene arreglo", "Me equivoqué: volver a «en revisión»") y el **siguiente paso**: devolver lo que sobra ("Ya le devolví $X", `servicios.devolver_saldo_a_favor`) o "Cobrar $X y entregar" / "Entregar al cliente". La pista de una orden terminada sin arreglo llega al final.
- **Borrar lo cargado por error, como en el admin** (servicios: `quitar_pago`, `anular_devolucion`, `quitar_equipo`, `eliminar_orden`, `anular_venta_directa`, `eliminar_cliente`): solo en órdenes abiertas y nunca dejando dinero sin registrar.
- **Tipos de equipo** en una tabla (`TipoEquipo`, migración 0017) editable en el Catálogo.
- **Catálogo agrupado** (Equipos · Reparaciones · Productos · Pagos) y **textos explícitos en todos los botones** ("Agregar marca", "Guardar cliente", "Entregar al cliente y cerrar la orden"…).
- Alta rápida de modelo/reparación: la marca o categoría nueva se escribe en el mismo lugar con "+ Escribir una … nueva".
- Al elegir un producto, la cantidad se completa con 1. "Registrar un pago" y "Agregar un producto" van en recuadros de color como "Agregar reparación".
- Orden con todos los equipos no arreglables **y productos**: queda "Lista para entregar" (ver [diagrama v6](../MODULOS/diagrama-clases-modulos-1-a-3-v6.md) §4.2).
- **Equipo sin arreglo:** después de devolver la seña (si hubo), "Devolver el equipo al cliente" cierra la orden con una venta de $0 (`cerrar_orden` acepta `finalizada`). Esas órdenes siguen "en curso" y aparecen en Entregar hasta devolver el equipo.
- **Venta rápida:** el resumen muestra el recargo de cada método y "El cliente paga $X".
- **Registro de ventas** (antes "Ventas"): con qué se cobró cada venta, cuánto entró con recargo y los totales del período por cuenta (efectivo / digital).

## Cambios del 18/11/2026 (tarde)

- Precio con lápiz: todo el recuadro es tocable (antes había que tocar justo el lápiz).
- Registro de ventas: columna **Tipo** (Orden #N / Venta rápida) y, en las órdenes, también los productos que se llevó.
- «Revisión / diagnóstico» va **una sola vez por equipo**: solo la primera fila la ofrece y el servidor lo controla (`Reparacion.es_revision`).
- Las devoluciones son del precio **sin recargo**: el recargo de la tarjeta lo devuelve la plataforma (se aclara en pantalla).
- "Catálogo" pasa a llamarse **Configuración** (grupo "Ajustes" del menú). Las direcciones siguen en `/catalogo/`.
- **Imprimir** en la orden abre dos opciones: *la orden* (una hoja, sin devoluciones) y *el comprobante para el cliente* (media hoja con condiciones; el texto de las condiciones es de ejemplo hasta tener el contrato).
- Pendiente para estadísticas: ver solo productos ([diagrama v6](../MODULOS/diagrama-clases-modulos-1-a-3-v6.md), §5.4 #22).
