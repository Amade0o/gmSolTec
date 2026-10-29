# GMSol — Diagrama de clases (v5, módulos 1 a 3 hasta la Venta)

> **Uso:** documento autosuficiente para cargar como contexto. **Reemplaza** a `diagrama-clases-modulo1y2-orden.md` (v4). Complementa a `GMSol-modelo-BPMN-taller-v2.md`, `GMSol-stack-y-arquitectura.md` y `0_Plan.md`.
> **Estado:** módulos 1 (catálogo) y 2 (orden de trabajo) cerrados. Módulo 3 (pagos y ventas): `MetodoPago`, `Pago`, `Venta`, líneas de venta directa y dinero retenido hechos y con tests (Fase 2, pasos 1 a 4). Falta el cierre de orden (paso 5) y la venta directa (paso 5b). Pruebas manuales en el admin en curso. Faltan los módulos 4 y 5 (caja y movimientos, compras).
> **Código:** las clases del diagrama están en `catalogo/models.py`, salvo `Producto.codigo`, `Proveedor`, `Configuracion`.
> **Vocabulario:** **Venta** = registro interno que cierra una transacción e impacta stock y caja (antes "factura"). **Comprobante ARCA** = documento legal, es otra cosa (etapa 8).
> **Leyenda:** ✅ decisión del desarrollador · 💡 propuesta (falta confirmar) · ❓ pendiente

---

## 1. Diagrama

```mermaid
classDiagram
  class Cliente {
    nombre
    notas
    email
    direccion
  }
  class Telefono {
    numero
    principal
  }
  class Proveedor {
    nombre
    contacto
    cuenta_corriente
  }
  class Configuracion {
    margen_por_defecto
  }
  class CategoriaProducto {
    nombre
    activa
  }
  class Producto {
    codigo
    nombre
    precio_compra
    precio_venta
    activo
  }
  class Marca {
    nombre
    activa
  }
  class ModeloEquipo {
    nombre
    tipo
    activo
  }
  class CategoriaReparacion {
    nombre
    activo
  }
  class Reparacion {
    nombre
    activo
  }
  class OrdenTrabajo {
    numero id automatico
    fecha_recepcion
    estado calculado
    cerrada calculado
    total calculado
    monto_pagado calculado
    monto_adeudado calculado
    adeuda calculado
    monto_retenido calculado
  }
  class EquipoRecibido {
    tipo
    problema
    tipo_bloqueo
    clave_bloqueo
    accesorios_dejados
    estado
  }
  class LineaReparacion {
    precio_vendido
    nota
  }
  class LineaProductoAbstracta {
    <<abstract>>
    cantidad_adquirida
    precio_vendido
    subtotal calculado
  }
  class LineaProductoOrden
  class LineaProductoVenta
  class MetodoPago {
    nombre
    cuenta
    recargo_porcentaje
    activo
  }
  class Pago {
    monto
    recargo_porcentaje
    fecha
    recargo_monto calculado
    total_cobrado calculado
    retenido calculado
  }
  class Venta {
    fecha
    total
  }

  Cliente "1" -- "0..n" Telefono
  CategoriaProducto "1" -- "0..n" Producto
  Producto "0..n" -- "0..1" Marca
  Marca "1" -- "0..n" ModeloEquipo
  CategoriaReparacion "1" -- "0..n" Reparacion
  Cliente "1" -- "0..n" OrdenTrabajo
  OrdenTrabajo "1" -- "1..n" EquipoRecibido
  EquipoRecibido "1" -- "1..n" LineaReparacion
  EquipoRecibido "0..n" -- "0..1" ModeloEquipo
  Reparacion "1" -- "0..n" LineaReparacion
  LineaProductoAbstracta <|-- LineaProductoOrden
  LineaProductoAbstracta <|-- LineaProductoVenta
  OrdenTrabajo "1" -- "0..n" LineaProductoOrden
  Venta "1" -- "0..n" LineaProductoVenta
  Producto "1" -- "0..n" LineaProductoOrden
  Producto "1" -- "0..n" LineaProductoVenta
  MetodoPago "1" -- "0..n" Pago
  OrdenTrabajo "0..1" -- "0..n" Pago
  Venta "0..1" -- "0..n" Pago
  Venta "0..1" -- "0..1" OrdenTrabajo
  Cliente "0..1" -- "0..n" Venta
  note for Pago "Pertenece a una orden O a una venta"
```

**Cómo se lee una cardinalidad:** el número junto a una clase dice cuántos objetos de *esa* clase se relacionan con **uno** del otro lado. Ejemplo: `Venta "0..1" -- "0..n" Pago` = una venta tiene de 0 a n pagos; un pago tiene 0 o 1 venta.

`Proveedor` y `Configuracion` no tienen relaciones por ahora. El número de la orden es su `id` y `fecha_recepcion` se completa sola (no admite fechas pasadas).

---

## 2. Clases (solo lo que no se ve en el diagrama)

| Clase | Módulo | Nota |
|---|---|---|
| Cliente | 1 | ✅ Obligatorios: nombre y teléfono (regla suave, ver §4). Opcionales: email y dirección. Sin DNI. ❓ `codigo`: decidir si se mantiene |
| Telefono | 1 | ✅ Clase separada, con `principal`. ❓ Falta etiqueta y regla de un solo principal |
| Proveedor | 1 | ❓ "Otros datos" sin definir. Se usa en el módulo 5 |
| Configuracion | 1 | ✅ Un solo margen por defecto para todos los productos |
| CategoriaProducto | 1 | ✅ Editable por el dueño. Incluye una categoría genérica |
| Producto | 1 | ✅ Los accesorios son productos. Las variantes van como productos distintos. `codigo` visible y editable; el `id` es interno |
| Marca | 1 | ✅ Compartida entre productos y modelos de equipo |
| ModeloEquipo | 1 | ✅ Modelo del equipo que se repara (celular o notebook) |
| CategoriaReparacion | 1 | ✅ Editable. Agrupa variantes de una reparación para estadísticas. Incluye una genérica |
| Reparacion | 1 | ✅ Catálogo de reparaciones. **Sin precio**. Incluye "Revisión / diagnóstico" |
| OrdenTrabajo | 2 | ✅ Un trabajo por visita. Siempre tiene al menos un equipo. No guarda estado: lo calcula (§4) |
| EquipoRecibido | 2 | ✅ Guarda el `estado` (`pendiente`, `arreglado`, `no_arreglable`, `sin_falla`). La PC va sin modelo |
| LineaReparacion | 2 | ✅ Reparación del catálogo acordada para un equipo, con **precio de esa orden** |
| LineaProductoAbstracta | 3 | ✅ **Clase abstracta, sin tabla.** Comparte `cantidad_adquirida`, `precio_vendido` (copiado del producto y editable), `producto` y `subtotal` |
| LineaProductoOrden | 3 | ✅ Hija: producto agregado a una orden de trabajo (FK `orden_trabajo`) |
| LineaProductoVenta | 3 | ✅ Hija: producto de una venta directa (FK `venta`) |
| MetodoPago | 3 | ✅ Editable por el dueño. `cuenta` es enumeración: `efectivo` o `digital`. `recargo_porcentaje` es el valor **sugerido** |
| Pago | 3 | ✅ Dinero contra el total de una orden o de una venta (no contra un producto). `monto` = lo que ingresa al negocio. `recargo_porcentaje` es una **copia editable** del método, queda como foto |
| Venta | 3 | ✅ Registro interno que cierra una orden (`orden_trabajo`, uno a uno) o es venta directa (sin orden). `total` es una **foto**. `cliente` opcional |

---

## 3. Relaciones

| Relación | Cardinalidad | `on_delete` en el código | Regla |
|---|---|---|---|
| Cliente — Telefono | 1 — 0..n | `CASCADE` | ✅ Regla suave (§4) |
| CategoriaProducto — Producto | 1 — 0..n | `PROTECT` | Un producto tiene una sola categoría |
| Producto — Marca | 0..n — 0..1 | `PROTECT` | ✅ Marca opcional |
| Marca — ModeloEquipo | 1 — 0..n | `PROTECT` | |
| CategoriaReparacion — Reparacion | 1 — 0..n | `PROTECT` | |
| Cliente — OrdenTrabajo | 1 — 0..n | `PROTECT` | Toda orden tiene cliente |
| OrdenTrabajo — EquipoRecibido | 1 — 1..n | `CASCADE` | ✅ Al menos un equipo (se valida en la pantalla) |
| EquipoRecibido — LineaReparacion | 1 — 1..n | `CASCADE` | Todo equipo lleva al menos una línea |
| EquipoRecibido — ModeloEquipo | 0..n — 0..1 | `PROTECT` | La PC no lleva modelo |
| Reparacion — LineaReparacion | 1 — 0..n | `PROTECT` | |
| OrdenTrabajo — LineaProductoOrden | 1 — 0..n | `CASCADE` | La línea es parte de la orden |
| Venta — LineaProductoVenta | 1 — 0..n | `CASCADE` | La línea es parte de la venta directa |
| Producto — LineaProductoOrden / LineaProductoVenta | 1 — 0..n | `PROTECT` | `related_name="%(class)ss"` en la base abstracta, para que las dos hijas no choquen |
| MetodoPago — Pago | 1 — 0..n | `PROTECT` | |
| OrdenTrabajo — Pago | 0..1 — 0..n | `PROTECT` | La seña entra antes de que exista la Venta, por eso cuelga de la orden |
| Venta — Pago | 0..1 — 0..n | `PROTECT` | Pagos de una venta directa |
| Venta — OrdenTrabajo | 0..1 — 0..1 | `PROTECT` (uno a uno, `related_name="venta"`) | Una orden tiene a lo sumo una venta; una venta directa no tiene orden |
| Cliente — Venta | 0..1 — 0..n | `PROTECT` | ✅ Cliente opcional en venta directa. En una reparación se copia el de la orden al cerrar |

Todas las relaciones se dibujan en ambos sentidos y no se dibujan las derivables. Criterio de `on_delete`: `CASCADE` cuando la clase es **parte de** otra; `PROTECT` cuando apunta a un dato que no debe desaparecer si está en uso.

---

## 4. Reglas de diseño

### 4.1 Heredadas (módulos 1 y 2)

| Regla | Detalle |
|---|---|
| **Nada se borra, se desactiva** | `activa` / `activo` en las clases editables |
| **El margen no se guarda** | Se calcula; `Configuracion.margen_por_defecto` solo sugiere el precio de venta |
| **Enumeraciones** | Tipo de equipo, tipo de modelo, estado del equipo, tipo de bloqueo y cuenta del método de pago. Valor interno simple (`contrasena`, `ninguno`) y etiqueta legible |
| **Orden en tres niveles** | OrdenTrabajo → EquipoRecibido → LineaReparacion |
| **Precio por orden** | Las líneas guardan su propio precio: órdenes y ventas viejas no cambian |
| **Problema, accesorios y clave** | Texto libre. Los accesorios que deja el cliente son una nota, no productos. La clave se guarda tal cual (login + backups cifrados) |
| **Categorías genéricas** | Toda reparación y todo producto tiene categoría obligatoria; existe "Otras" |
| **Equipo sano o sin diagnóstico** | Todo equipo lleva al menos una línea ("Revisión / diagnóstico"); si no tiene falla queda `sin_falla` |
| **Teléfono: regla suave** | Se pide siempre, se puede guardar sin él confirmándolo; el sistema lista los clientes sin teléfono |
| **Nombres** | Español. PascalCase para clases, snake_case para atributos |

### 4.2 Estados de la orden (calculados, nunca guardados)

| Estado | Cuándo |
|---|---|
| `pendiente` | Algún equipo está pendiente (o no hay equipos) |
| `no_arreglable` | Todos los equipos son `no_arreglable`. **No genera Venta**: la orden queda registrada con ese estado y el dinero se devuelve (Fase 5) |
| `lista` | Ningún equipo pendiente y no todos son no arreglables |
| `cerrada` | 💡 Tiene una Venta (paso 4 de la Fase 2). Retiro y venta son el mismo acto |

### 4.3 Dinero (módulo 3)

| Regla | Detalle |
|---|---|
| **Dos datos por pago** | *Por dónde entró* (`MetodoPago.cuenta`: efectivo o digital) y *estado del dinero* (🔒 retenido · ⏳ pendiente de acreditar · ✅ disponible). Efectivo y digital son **dos cuentas de la caja**, no un "retiro" como en el Excel del dueño |
| **Retenido** | Todo pago de una orden está retenido hasta que la orden se cierra. `Pago.retenido` y `OrdenTrabajo.monto_retenido` **se calculan**. Los pagos de venta directa nunca están retenidos |
| **Recargo** | `Pago.recargo_porcentaje` se copia del método al crear (si viene vacío) y se puede cambiar. `recargo_monto = monto × % / 100`; `total_cobrado = monto + recargo` (lo que paga el cliente) |
| **Montos de la orden** | `monto_pagado` suma `Pago.monto` (sin recargo). `monto_adeudado = total − monto_pagado`. `adeuda = monto_adeudado > 0` |
| **Pago y productos** | Un pago no se relaciona con productos: es dinero contra el total. Un cargador pagado mitad efectivo y mitad tarjeta son dos pagos sobre la misma venta |
| **Un pago, un dueño** | Un `Pago` pertenece a una orden **o** a una venta. 💡 `Pago.clean()` rechaza que tenga las dos; una restricción en la base rechaza las dos y ninguna (en el admin, al crear una orden nueva la FK a la orden todavía no existe cuando corre `clean()`, por eso "ninguna" no se valida ahí) |
| **Pago ≤ adeudado** | Se valida en el formulario (etapa 7) |
| **ARCA** | `facturar_arca` en cada pago, etapa 8 |

### 4.4 Venta (módulo 3)

| Regla | Detalle |
|---|---|
| **Qué es** | Cierra una orden de reparación o es una venta directa. No genera ticket para el cliente |
| **Venta de reparación** | Se vincula a la orden (uno a uno). Líneas y pagos quedan en la orden. `total` se copia de `orden.total` al crear. `cliente` se copia de la orden |
| **Venta directa** | Sin orden. Sus productos son `LineaProductoVenta` y sus pagos son `Pago` con `venta`. `total` = suma de sus líneas |
| **Condiciones de cierre** | Orden: estado `lista` y sin deuda. Venta directa: pagada completa (la Fase 3 lo relaja para fiados) |
| **Orden cerrada no se edita** | Ni líneas ni pagos |
| **Clases hermanas, no campo opcional** | Las líneas de producto se dividen en dos clases con base abstracta, así ninguna línea tiene dos dueños posibles |
| **Producto al retirar** | Si no se registra en la orden, es una venta directa aparte (BPMN, Call Activity) |
| **Stock y caja** | La Venta **no** los toca en esta etapa. Se descuentan al registrar la Venta, en una sola transacción (etapa 4). Stock disponible = físico − reservado en órdenes abiertas (calculado) |

---

## 5. Pendientes

### 5.1 Hecho ✅

| Tema | Resultado |
|---|---|
| Paso 1 y 2 de la Fase 2 | `LineaProductoAbstracta` con `LineaProductoOrden` y `LineaProductoVenta`; `Venta`; `Pago.venta`. Migrado |
| Paso 3 | Un pago pertenece a una orden **o** a una venta: `Pago.clean()` (no ambas) más restricción en la base (ni ambas ni ninguna) |
| Paso 4 | `OrdenTrabajo.cerrada`, estado `cerrada`, `monto_retenido` y `Pago.retenido`. Con tests |
| Nombre del precio | `precio_vendido` unificado en `LineaReparacion` y en las líneas de producto |
| `Venta.orden_trabajo` | `related_name="venta"` (uno a uno). `Venta.cliente` queda con `ventas_cliente` |

### 5.2 En curso 🔄

| # | Tema |
|---|---|
| 1 | Paso 5: `servicios.cerrar_orden` (valida y crea la Venta), acción en el admin y tests. Código propuesto, falta implementar |
| 2 | Pruebas manuales en el admin con `checklist-pruebas-admin.md`; el feedback decide los puntos de 5.3 |
| 3 | Paso 5b (después de las pruebas): venta directa, con `LineaProductoVenta` y `Pago` en una sola transacción |

### 5.3 Nuevos, surgidos al probar el admin

| # | Tema | Detalle | Se resuelve en |
|---|---|---|---|
| 4 | **PIN y patrón visuales** | Hoy `clave_bloqueo` es texto. El patrón necesita una grilla de 9 puntos que se toca y guarda `1-5-9-6`. 💡 Mientras tanto, validar el formato según `tipo_bloqueo` (pin: dígitos; patrón: dígitos 1 a 9 sin repetir; ninguno: vacío) | Widget en la etapa 7; validación, antes |
| 5 | **Precio en la línea de producto** | El diseño dice que se copia de `Producto.precio_venta` y se puede cambiar, pero hoy hay que escribirlo. 💡 Copiarlo al guardar si viene vacío (como el recargo del `Pago`). El subtotal en vivo necesita JavaScript | Copia: ahora. Subtotal en vivo: etapa 7 |
| 6 | **Orden en una sola pantalla** | El admin no anida dos niveles (orden → equipo → línea), así que al crear la orden no se puede cargar el precio de la reparación y los pagos quedan sin total. Las líneas de reparación van por su propia pantalla | Pantalla propia, etapa 7 (con alta de reparación "al vuelo") |
| 7 | **Seña antes de saber el precio** | ❓ Con total 0 y una seña, `monto_adeudado` queda negativo y la validación "pago ≤ adeudado" la rechazaría. 💡 Validar solo cuando el total sea mayor que 0 (la línea "Revisión / diagnóstico" cubre el caso de precio desconocido) | Etapa 7, junto con la validación |
| 8 | **Líneas sueltas en el admin** | ❓ `LineaReparacion` suelta hace falta por ahora (punto 6). `LineaProductoOrden` y `LineaProductoVenta` ya se cargan en su inline: sacarlas o dejarlas de solo lectura. Hoy permiten editar líneas de una orden cerrada | Admin: ahora. Blindaje en el modelo: etapa 6 |
| 9 | **Nombres únicos** | ❓ Único: `MetodoPago.nombre`, `CategoriaProducto.nombre`, `CategoriaReparacion.nombre`, `Marca.nombre`, `Proveedor.nombre`. Único por pareja: `Reparacion` (categoría y nombre), `ModeloEquipo` (marca y nombre), `Producto` (nombre, o nombre y marca). **No** único: `Cliente.nombre`, `Telefono.numero` | Ahora (restricciones en la base) |
| 10 | **Reparación vs categoría de reparación** | No es un error: la categoría es el tipo ("Cambio de módulo") y la reparación es la variante ("Módulo OLED", "Módulo original"). Una categoría sin variantes obliga hoy a crear una reparación con el mismo nombre. 💡 `ReparacionInline` en el admin de la categoría; en la pantalla propia, crear categoría y variante en un solo paso; precargar las comunes en la etapa 11 | Admin: ahora. Resto: etapas 7 y 11 |
| 11 | **Huecos por verificar con el checklist** | Sin validador de mínimo en `Producto.precio_compra` y `precio_venta`; marcas y categorías inactivas siguen apareciendo en altas nuevas; dos teléfonos principales; una Venta creada a mano en el admin se saltea el cierre; borrar una Venta reabre la orden | Según el feedback |

### 5.4 Pendientes de fases y etapas futuras (sin cambios)

| # | Tema |
|---|---|
| 12 | Fase 3: `monto_pagado` y `monto_adeudado` en `Venta` (fiados) y cliente obligatorio si queda saldo |
| 13 | Fase 4: pagos ⏳ con fecha de acreditación (GoCuotas, tarjeta diferida) |
| 14 | Fase 5: devoluciones. ❓ Orden mixta (un equipo no arreglable): sus líneas no deberían cobrarse. ❓ Estado final de una orden no arreglable |
| 15 | ❓ Transiciones: ¿volver de `arreglado` a `pendiente`? Estado "esperando repuesto". Historial de estados (tabla que solo se agrega) |
| 16 | ❓ Costo del repuesto en cada línea de reparación (ganancia) |
| 17 | ❓ `Producto.codigo`, `Cliente.codigo`, datos de `Proveedor`, margen por categoría, teléfono (etiqueta y un solo principal) |
| 18 | ❓ Blindar en la base las reglas de cantidad y precio |
| 19 | Módulos 4 y 5: caja y movimientos, compras y proveedores |

---

> **Me gusta que me preguntes si quiero avanzar al siguiente paso o no, antes de avanzar.**
