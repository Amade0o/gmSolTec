# GMSol — Modelo BPMN del proceso de reparación y venta

Documento de referencia para el modelo BPMN dibujado en pizarra (servicio técnico + venta de productos). Resume las decisiones de diseño acordadas y las correcciones hechas sobre versiones anteriores del diagrama.

---

## 1. Alcance del modelo

El BPMN cubre **únicamente** dos procesos: reparación de dispositivos (celular, PC, notebook) y venta de productos. No modela: facturación a ARCA, estadísticas, caja, ni la impresión/firma física de la orden — esos son requisitos aparte, no parte de este diagrama.

Dos pools: **Cliente** y **Comercio**.

---

## 2. Entradas al proceso (pool Cliente)

El cliente puede iniciar contacto de dos formas independientes, **sin gateway que las una**:

- **"Solicita producto ya"** — evento de inicio de mensaje propio.
- **"Solicita reparación"** — evento de inicio de mensaje propio.

**Decisión clave:** no se usa un gateway paralelo (ni exclusivo) para unir estas dos solicitudes. Son dos eventos de inicio separados porque el mismo cliente puede dispararlas en cualquier orden y cualquier cantidad de veces (comprar algo al llegar, después pedir una reparación, y al retirar el equipo comprar otro producto suelto). Un gateway al inicio forzaría a tratarlas como una sola decisión, lo cual no refleja el comportamiento real.

La pool Cliente se simplificó a propósito: no modela cómo decide el cliente (sí/no, elección de método de pago), solo los puntos de entrada. Esas decisiones intermedias se resuelven como gateways normales dentro de la pool Comercio.

---

## 3. Camino "solicita producto ya"

1. **Se consulta stock**
2. Gateway (exclusivo) — **¿Hay stock?**
   - **No** → Notificar cliente que no hay stock → fin
   - **Sí** → **Presupuestar y acordar venta** (subproceso colapsado) → gateway ¿acepta presupuesto? → no: fin / sí: continúa
3. **Acordar método de pago** (subproceso colapsado)
4. **Crear factura**
5. **Actualizar BDD** (precio, stock, registro) → fin

> Nota de diseño abierta: hay una flecha duplicada entre "Acordar método de pago" y "Crear factura" (una versión con doble punta y otra simple) que está pendiente de resolver — decidir si esas dos tareas se separan (recomendado, para no perder la frontera entre "negociación con el cliente" y "registro interno") o se fusionan.

Esta rama es exactamente la misma que se dispara desde el punto 6 (ver más abajo) cuando el cliente agrega un producto al retirar el equipo pero no quiere que se registre en la misma orden.

---

## 4. Camino "solicita reparación"

1. **Se consulta stock proveedor**
2. Gateway (exclusivo) — **¿Hay stock?**
   - **No** → Notificar cliente que no hay stock → fin
   - **Sí** → **Presupuestar y acordar reparación** (subproceso colapsado) → gateway ¿acepta presupuesto? → sí: continúa
3. **Preparar orden, cargar reparación**
4. **Consultar si desea agregar accesorios** (subproceso colapsado)

### 4.1 Sub-flujo de accesorios (opcional, dentro del punto 4)

Los accesorios son **solo los relacionados a la reparación** (cable/cargador, funda, templado, teclado según el dispositivo) — nunca productos sueltos sin relación al arreglo.

1. **Consultar accesorio a agregar** (subproceso colapsado)
2. **Consultar stock**
3. Gateway exclusivo — **¿Hay stock?**
   - **No** → Notificar cliente que no hay stock (de ese accesorio puntual) → el flujo **continúa igual**, no cancela la orden de reparación
   - **Sí** → **Presupuestar y acordar accesorio** (subproceso colapsado) → gateway ¿desea agregar? → sí: **Actualizar orden con producto** / no: sigue directo
4. Cierre del gateway exclusivo (todas las ramas convergen antes de seguir)

**Regla de negocio importante:** la falta de stock de un accesorio opcional (templado, cable) **nunca cancela la orden de reparación**. Solo se notifica y se sigue sin ese ítem. Esto es distinto del caso "no se encontró el repuesto necesario para reparar" (ver pendientes, sección 7).

### 4.2 Continuación tras el cierre de accesorios

5. **Acordar método de pago y porcentaje de pago** (subproceso colapsado) — acá se decide si el cliente paga el total o deja una seña, y con qué método. Es distinto del acuerdo de pago del cierre (punto 6), que solo cubre el saldo restante.
6. **Actualizar orden con pago**
7. **Arreglar siguiendo orden de reparación, marcar como listo** (arreglable / no arreglable)
8. Gateway exclusivo — **¿Desea notificar al cliente del arreglo terminado?**
   - Sí → Notificar cliente servicio terminado
   - No → sigue directo (converge con la rama anterior)
9. **Consultar y desea agregar productos** (subproceso colapsado) — última oportunidad de agregar algo al retirar

---

## 5. Cierre de la orden (retiro del dispositivo)

Después del punto 9:

1. Gateway exclusivo — **¿Desea registrarlo en la orden?**
   - **Sí** → sigue el cierre normal de la orden (punto 2 de esta sección)
   - **No** → dispara **"Solicitar producto ya"** como **Call Activity independiente**, con su propio evento de fin. No bloquea ni espera el cierre de la orden de reparación — son dos procesos que corren en paralelo sin sincronizarse entre sí (se descartó el AND-join que se había considerado en una versión anterior, porque no hace falta que ambos terminen juntos).

2. **Verificar si adeudo pago**
3. Gateway exclusivo — **¿Adeuda?**
   - **No** → converge directo a "Generar factura de la orden"
   - **Sí** → **Acordar método de pago** (subproceso colapsado, segundo uso — cubre solo el saldo pendiente) → **Registrar pago total** → converge a "Generar factura de la orden"
4. **Generar factura de la orden**
5. **Actualizar BDD** (precio, stock, registro) → fin

---

## 6. Decisiones de diseño acordadas (resumen conceptual)

- **Orden y factura son documentos distintos.** La orden se le entrega al cliente al dejar el dispositivo; la factura es el registro de la transacción cerrada. Se generan en momentos distintos del proceso.
- **Subprocesos colapsados** para todo intercambio repetitivo de "proponer algo → cliente responde sí/no" (presupuestos, accesorios, método de pago), en vez de dibujar cada mensaje ida y vuelta. Esto bajó drásticamente la complejidad visual del diagrama.
- **Call Activity** reservada para procesos que se **reutilizan como unidad completa** en más de un punto del diagrama (caso "Solicitar producto ya", invocado desde el inicio y desde el cierre de la orden).
- **Gateways exclusivos (X), no paralelos (+), para toda decisión sí/no** — incluida la convergencia después de la rama de accesorios, porque agregar o no agregar es una decisión mutuamente excluyente, no dos caminos que deban ejecutarse juntos.
- **Pago en dos momentos posibles:** seña/total al dejar el equipo (con su propio acuerdo de método y porcentaje) y saldo al retirar (con un segundo acuerdo de método, solo si adeuda). Son subprocesos separados porque ocurren en momentos distintos y bajo distintas condiciones.
- **Falta de stock de accesorio ≠ falta de stock de repuesto necesario.** Solo la segunda debería poder bloquear la orden (queda como tarea pendiente formalizar esa distinción en el modelo, ver sección 7).
- **Simplificación de la pool Cliente:** no se modelan los mensajes intermedios de ida y vuelta ni las decisiones del cliente como eventos de mensaje explícitos; se resuelven como gateways dentro de la pool Comercio.

---

## 7. Nota pendiente

> Faltan agregar algunas funciones como "¿Desea facturar?" o el plazo de 30 días (disclaimer de reclamos de la orden física). Están identificadas pero todavía no incorporadas al diagrama.
