# GMSol — Decisiones para el diagrama de clases (v1)

> **Uso:** documento autosuficiente para cargar como contexto. Complementa a [BPMN.md](../BPMN%20Y%20MODELO/BPMN.md) y [stack_tecnologico.md](stack_tecnologico.md).
> **Qué es:** cada decisión responde una pregunta concreta hecha al empezar el modelado de clases.
> **Leyenda:** ✅ decisión del desarrollador · 💡 implicación de diseño propuesta (falta confirmar) · ❓ pendiente

---

## 1. Decisiones sobre el negocio

### 1.1 ¿Una orden puede tener varios dispositivos a la vez, o uno por orden?
✅ **Puede tener varios dispositivos.**
💡 Orden 1 → N Dispositivos de la orden. Cada uno lleva su propio daño, tipo de bloqueo y reparaciones.

### 1.2 ¿En la venta directa se registra el cliente o puede ser anónimo?
✅ **Los clientes se guardan en base de datos con todo el registro posible.**
❓ **Preocupación:** dos clientes con el mismo nombre (ej.: dos "Juan Perez") que el dueño pueda confundir.
Se puede poner que una venta no tiene cliente asignado pero igualmente necesito el registro de esa venta que vaya a "ningun" cliente. Una solucion a la preocupacion es que se utilicen IDs para los clientes pero el problema es que mi papá se guia de los clientes por su nombre y su cara asique sería un problema ya que no puede recordar todos los ids... Me parece poco urgente igualmente solucionar esto

### 1.3 ¿La reparación es un catálogo con precio o texto libre con monto?
✅ **Catálogo de reparaciones, organizado de antemano**, para que las estadísticas sean posibles. Un texto libre haría imposible contar qué reparaciones se hicieron. Se pueden **agregar y quitar**.
💡 Al "quitar" una reparación del catálogo, que quede desactivada (no borrada), para no romper órdenes y estadísticas históricas.

### 1.4 ¿Usar un repuesto en una reparación descuenta stock?
✅ **No, por ahora.** El dueño no compra repuestos para guardar. La idea a futuro es usar las **estadísticas (filtrables por fecha)** para decidir qué repuestos conviene tener en stock.
💡 Dejar el diseño **preparado** para agregar después una sección de stock de repuestos, sin reescribir lo existente.

### 1.5 ¿Accesorios y productos son lo mismo?
✅ **Sí, los accesorios son productos.** Misma categoría, se manejan por stock. Solo se separaron en el BPMN para que el flujo se entienda mejor.
💡 No hay clase "Accesorio" aparte: es un Producto.

### 1.6 ¿El recargo por tarjeta se cobra y registra junto o aparte?
✅ **Va anotado en la venta y modifica el total** (queda junto).

### 1.7 ¿Se genera una venta por orden, o puede registrarse solo un pago?
✅ **Se registran ambas ventas. lo que se debe poder decidir si facturarse o no es lo del ARCA, no todas las ventas del programa irán al arca, recuerda eso**

### 1.8 Si cambia el precio de un producto, ¿las ventas viejas conservan el precio?
✅ **Sí, conservan el precio de ese momento** (evita que cambien ventas antiguas, sobre todo por la inflación).
💡 La línea de venta guarda una copia del precio, no una referencia al precio actual del producto.

### 1.9 ¿Se registran las compras a proveedores o solo los pagos?
✅ **Se registran ambas cosas.**

### 1.10 ¿Las devoluciones aplican solo a reparaciones no arreglables o también a productos?
✅ **Aplican a ambos**, pero las devoluciones de productos **no son prioridad**.

### 1.11 4. El problema del cable
¿Que pasa si hago la orden, le guardo un cable aun cliente pero como no se lo dí entonces no se facturó entonces no se fue del stock. Quizá ya se lo dí cuando vino a dejar el telefono?

La solución es separar dos números, y el segundo se calcula, como el margen:

Disponible = Stock físico − Reservado en órdenes abiertas

Se descuenta físicamente recién al registrar la venta, como ya tenías decidido.
Queda un caso borde para más adelante: equipo no arreglable pero el cable ya se entregó. Según el BPMN ese camino no genera venta, habría que cobrar el cable aparte.

---

## 2. Decisiones de estilo

### 2.1 ¿Nombres de clases en español o inglés?
✅ **Español, por ahora.**

### 2.2 ¿Pocas clases simples o más clases chicas y especializadas?
❓ **No está seguro.** Se resuelve con ejemplos concretos durante el modelado.

### 2.3 ¿En qué formato va el diagrama?
✅ **Mermaid dentro del .md.**

---

## 3. Plan de trabajo acordado

| # | Módulo |
|---|---|
| 1 | Catálogo: Producto, Cliente, Proveedor, Marca/Modelo de dispositivo, catálogo de reparaciones |
| 2 | Orden de trabajo y sus estados |
| 3 | Ventas, pagos y registro de ventas |
| 4 | Caja y movimientos (dinero y stock) |
| 5 | Compras a proveedores |

Las **estadísticas** no son clases nuevas: son consultas sobre lo anterior, pero el diseño debe hacerlas posibles.

---

## 4. Forma de trabajar

- Prioridad: el **entendimiento propio** y el **estilo propio** del desarrollador (Claude lo va aprendiendo). Se siguen buenas prácticas y se exige rigor, pero las decisiones finales son del desarrollador.
- Cada decisión se presenta con opciones, pros y contras.
- Cada patrón se justifica con un problema concreto del negocio.

> **Me gusta que me preguntes si quiero avanzar al siguiente paso o no, antes de avanzar.**
