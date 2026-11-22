# GMSol — Etapa 4: caja, stock y fiados (v1)

> **Uso:** documento de diseño para cargar como contexto. Complementa a [0_Plan.md](../MODULOS/0_Plan.md), al [diagrama de clases v6](../MODULOS/diagrama-clases-modulos-1-a-3-v6.md), a [notas_respecto_a_pagos.txt](../NOTAS_PERSONALES/notas_respecto_a_pagos.txt) y a [etapa-7-interfaz.md](etapa-7-interfaz.md).
> **Estado (21/11/2026):** decisiones cerradas con el desarrollador (queda abierta la §3.3). Nada de esto está programado todavía.
> **Leyenda:** ✅ decidido por el desarrollador · 💡 propuesta (falta confirmar) · ❓ pregunta abierta

---

## 1. Principios

| # | Principio | Por qué |
|---|---|---|
| 1 | ✅ **La caja es lo más delicado del programa:** tiene que ser lo más claro y lo más seguro | Es el dinero del cliente |
| 2 | ✅ **El saldo de cada caja es la suma de una sola tabla** (`MovimientoCaja`), sin excepciones | Una sola cuenta, fácil de explicar y de testear |
| 3 | ✅ **El dueño corrige y anula con botones normales; por detrás nada se pierde** | Él no tiene que saber contabilidad. Cada cambio queda en el historial, escrito en palabras |
| 4 | ✅ **Nunca mostrar un dato que pueda estar mal.** Cada número dice qué es y de cuándo es | Inflación, datos incompletos, conteos viejos |
| 5 | ✅ **Ningún botón obliga a adivinar.** El texto dice la acción completa ("Registrar retiro de efectivo") y, antes de mover dinero, una confirmación repite monto, caja y motivo | Que no se maree |
| 6 | ✅ **El programa controla solo, sin depender del conteo físico diario** (el dueño no cuenta todos los días). Pregunta de vez en cuando, sin molestar | Ver §6 |
| 7 | ✅ **Primero funciona y se testea; la interfaz se pule al final** (pantallas mínimas para probar cada paso) | |

---

## 2. Cómo lo resuelven otros programas (investigación)

| Programa | Qué hace | Qué tomamos |
|---|---|---|
| **Odoo** (gestión de stock) | Un movimiento de stock hecho **no se edita ni se borra**: se corrige con un movimiento nuevo o con un ajuste de inventario, para no perder la trazabilidad | Lo de atrás: los movimientos quedan siempre |
| **Shopify** (stock) | Cada producto tiene su **historial de ajustes** con el motivo (venta, devolución, corrección, reposición) | El historial por producto, con motivo en palabras |
| **QuickBooks** (contabilidad) | Deja **editar** transacciones, pero guarda un **registro de auditoría** imposible de apagar, con el antes y el después | Lo de adelante: el usuario edita normalmente |
| **Square** (caja) | El cajón tiene "esperado" y "contado"; la diferencia se registra, **nunca se maquilla** el número esperado | "Conté y hay $X": el sistema calcula y guarda la diferencia |
| Prácticas de inventario | **Conteo cíclico:** en vez de contar todo, se cuentan pocos productos por vez, rotando | Las preguntas cortas de §6 |

**Conclusión ✅:** combinar lo de adelante de QuickBooks (editar fácil) con lo de atrás de Odoo (nada se pierde). Al dueño se le muestra "Corregir" y "Anular"; el sistema guarda el valor anterior y una frase en el historial.

---

## 3. Las cajas

| Caja | Qué tiene | Cómo se ve |
|---|---|---|
| **Efectivo** | Billetes del local, disponibles | Grande |
| **Digital** | Banco + Mercado Pago + Naranja X, todo junto (✅) | Grande. Con una sección "Más detalle" (§3.3) |
| **Señas** ✅ | Plata de órdenes abiertas que el dueño **no usa** (la aparta con el papelito) | Más chica y de otro color. Dividida en "en efectivo" y "en digital" |
| **A cobrar** ⏭️ | GoCuotas y tarjeta diferida: ya se vendió, todavía no entró | Chica, con la fecha en que debería entrar. **Después de la beta** (§8) |
| *Me deben* (no es caja) | Fiados: ventas y órdenes entregadas con saldo pendiente | Una lista, no un saldo: esa plata no está en ningún lado |

### 3.1 Lo retenido (señas) ✅

**Problema:** hoy un pago de una orden abierta queda "retenido" solo como un cálculo. El efectivo de la seña está apartado físicamente, pero una seña por transferencia ya está en el banco, mezclada con el resto.

**Propuesta:**
1. Todo pago de una **orden abierta** entra en la caja **Señas**, del lado de su cuenta (efectivo o digital).
2. Al **entregar** el equipo (la orden se cierra con la venta), el sistema **pasa** esa plata de Señas a Efectivo o Digital, en la misma operación. En el historial se lee: "La seña de la orden #12 ($5.000, efectivo) pasó a la caja".
3. Una **devolución** de una seña sale de Señas.
4. Los pagos de una venta rápida, de un fiado o de una orden ya cerrada van directo a Efectivo o Digital.
5. **Control automático:** Señas siempre tiene que ser igual a lo pagado en las órdenes abiertas, menos lo que se pasó a la caja con "Reservar solo la reparación". Si alguna vez no coincide, el programa avisa (§6).
6. **Para comparar con el banco:** "En el banco debería haber $X = Digital $A + señas en digital $B". Así el número coincide con lo que él ve en la app del banco.

**Reservar solo la reparación ✅ (decidido el 21/11/2026).** Lo retenido es para las reparaciones (por si no se arreglan); los productos no tienen por qué trabar la plata del local. Como en las órdenes el pago suele venir todo junto:
- **Por defecto se reserva todo** lo pagado en la orden (lo más simple).
- Debajo de la seña, la orden muestra una nota: *"De estos $12.000, la reparación es $9.000. Si querés, podés reservar solo eso y pasar $3.000 a la caja."* → botón **"Reservar solo la reparación"**.
- Si lo toca, el sistema pasa la diferencia de Señas a Efectivo o Digital (con su frase en el historial). Lo que queda en Señas nunca es menos de lo pagado para las reparaciones.
- Si después cambia la orden (se agrega una reparación, un equipo no tiene arreglo), la nota se recalcula y el control de §6.1 avisa si hace falta volver a reservar.
- Una venta rápida o una venta ya cerrada nunca se reserva.

### 3.2 Movimientos

`MovimientoCaja` 💡: fecha, caja, tipo, **monto con signo** (+ entra, − sale), descripción automática, nota del dueño, `anulado`, y de dónde viene (pago, devolución, venta, o nada si es manual).

| Tipo | Lo crea | Caja |
|---|---|---|
| Saldo inicial | El desarrollador, el día de la instalación | Efectivo, Digital |
| Pago de una orden abierta | Registrar pago | Señas |
| Pase de la seña al entregar | Entregar | Señas → Efectivo/Digital |
| Pago de una venta, de un fiado o del saldo al entregar | Venta rápida, cobrar, entregar | Efectivo, Digital |
| Reservar solo la reparación | Botón en la orden (§3.1) | Señas → Efectivo/Digital |
| Devolución | Marcar devuelta | La caja de donde sale (por el método, que deja de ser informativo ✅) |
| **Retiro del dueño** ✅ | Botón "Registrar retiro" | Cualquiera (sale "de todos lados") |
| Gasto del negocio | Botón "Registrar gasto" | Efectivo, Digital |
| Pago de mercadería | Botón "Registrar compra de mercadería" (lo mínimo de la etapa 5) | Efectivo, Digital |
| Pase entre cajas | "Pasé plata de efectivo a digital" (depósito) o al revés | Las dos |
| Ajuste por conteo | "Conté y hay $X" | La que se contó |

✅ Fuera por ahora: Gastos mensuales de la casa e inversiones (IOL).

**Saldo = suma de los movimientos no anulados de esa caja.** No hay otra cuenta.

### 3.3 "Más detalle" de digital 💡

Sin datos nuevos: cuánto entró por cada **método** (transferencia, débito, crédito, GoCuotas) en el período, recargos cobrados y retiros del período (lo "a cobrar" se suma cuando llegue GoCuotas). ❓ Separar banco / Mercado Pago / Naranja X necesitaría saber a cuál fue cada pago (un dato más al cobrar). ¿Lo vale?

---

## 4. Corregir y anular sin ser contador ✅

| Lo que ve el dueño | Lo que pasa por detrás |
|---|---|
| **"Corregir"** en un pago, retiro o gasto: cambia el monto, el método o la nota | Se cambia el movimiento y se guarda el **antes y el después** en el historial |
| **"Anular"** (cargado por error) | El movimiento queda marcado `anulado`: no suma, se ve tachado y el historial dice quién y cuándo. **Nunca se borra** |
| Los botones de hoy ("Quitar este pago", "Anular esta venta", "Eliminar esta orden") | Siguen iguales, pero ahora anulan en lugar de borrar y dejan su frase en el historial |

### 4.1 Historial ✅

**Tiene que ser lindo y fácil de leer para el dueño** (pedido del desarrollador): una línea de tiempo por día, con el ícono y el color de cada tipo (dinero, stock, órdenes), el monto destacado y el antes → después bien visible. No es una tabla técnica.


- Una pantalla **Historial** y, en cada orden, producto y caja, **"Ver los cambios de esto"**.
- Cada renglón es una frase: *"21/11 15:32 — Orden #12: corregiste el pago de $5.000 a $50.000 (efectivo). Antes decía $5.000."*
- Filtros: hoy / esta semana / este mes · dinero / stock / órdenes.
- El historial no se edita ni se borra.
- ✅ Sin reglas especiales en la base de datos (no hace falta protegerlo de ataques): alcanza con que el programa sea estable y todo pase por `servicios`.

---

## 5. Stock

### 5.1 Catálogo ≠ stock ✅

- **Catálogo** = qué se puede vender (nombre, categoría, marca, precios). Existe aunque haya 0.
- **Stock** = cuántas unidades hay. Cambia con cada venta, entrada o conteo.
- **Productos** muestra el catálogo con una columna **"Hay"**. Configuración queda para las tablas chicas (categorías, marcas, métodos de pago).

### 5.2 Reglas

| Regla | Detalle |
|---|---|
| ✅ Productos **sin control de stock** | Marca "No lleva stock" (ej.: carga virtual). No se cuentan ni bloquean |
| ✅ `MovimientoStock` | Producto, cantidad con signo, tipo (inicial, entrada de mercadería, venta, apartado en orden, vuelve de orden, corrección), fecha, nota, `anulado`. **Stock = suma** |
| ✅ **Sin stock no se vende** | El mensaje ofrece la salida: *"No hay Cargador 20W (quedan 0). Si en realidad tenés, corregí el stock primero."* → botón **"Corregir el stock de Cargador 20W"** |
| ✅ **"Corregir: conté y hay X"** | El dueño escribe **cuántos hay**, no la diferencia. El sistema calcula la diferencia y la guarda como corrección |
| ✅ Stock inicial | Se carga a mano el día de la instalación. La hoja "Stock" del Excel sirve de ejemplo para los datos de prueba |
| ✅ Costo en cada línea vendida | Copia de `precio_compra` al vender. Sirve para la rentabilidad (§7) sin depender del precio de hoy |

### 5.3 Productos de una orden ✅ opción A

Cuando se agrega un cargador a una orden de reparación, hay dos momentos posibles para descontarlo:
- **A)** Al agregarlo a la orden (se **aparta** del estante). Si se quita de la orden, vuelve al stock.
- **B)** Recién al entregar el equipo (hasta entonces figura como "reservado").

✅ **Se eligió A** (21/11/2026): es lo que pasa en la realidad (el cargador ya no está a la venta), da menos problemas y evita el número "reservado", que confunde. Si la orden se elimina o el producto se quita, el stock vuelve, con su frase en el historial.

---

## 6. Controles automáticos y preguntas al dueño

### 6.1 Controles que corren solos ✅

| Control | Si falla |
|---|---|
| Ninguna caja queda en negativo | No deja guardar: *"En efectivo hay $3.000; no pueden salir $5.000. ¿Salió de digital?"* |
| Señas = lo pagado en órdenes abiertas − lo pasado a la caja (§3.1) | Aviso en Inicio, con qué orden no coincide |
| Lo reservado de cada orden alcanza para sus reparaciones | Aviso en la orden: *"Hay que volver a reservar $X"* |
| Cada pago tiene su movimiento, con el mismo monto y la misma caja | Aviso en Inicio |
| Ningún stock en negativo | No deja vender (§5.2) |
| Fiados viejos | *"Juan Pérez debe $8.000 desde hace 45 días."* |

Una pantalla **"Revisar que todo esté bien"** corre todos los controles y dice, en palabras, que está todo bien o qué hay que mirar.

### 6.2 Preguntas de vez en cuando ✅ una vez por semana

Como no cuenta todos los días, el programa pregunta **poco y corto**, en Inicio, y se puede saltear:
- **Caja** (por ejemplo, una vez por semana): *"¿Hay $45.000 en efectivo?"* → **Sí** / **No, hay otra cantidad**. Si no coincide: *"Faltan $2.000. ¿Qué pasó?"* → [Saqué y no lo anoté] [Fue un gasto] [No sé, dejalo como diferencia].
- **Digital:** *"¿En el banco y Mercado Pago hay $120.000 en total?"* (con la cuenta de §3.1, punto 6).
- **Stock (conteo cíclico):** cada semana, 3 productos al azar entre los que más se venden: *"¿Tenés 4 Cargador 20W?"*.

✅ Una vez por semana para empezar (se puede cambiar después).

---

## 7. Rentabilidad con inflación ✅

Sumar pesos de meses distintos da un número engañoso. Propuesta:
- **Margen en porcentaje** de cada venta (precio contra costo de ese momento): un porcentaje no se deforma con la inflación como un monto.
- **Comparar meses en cantidades** (unidades vendidas, reparaciones hechas), no en pesos.
- Los pesos se suman **dentro del mismo mes**, aclarándolo.
- 💡 **Costo de reposición:** *"¿Con lo que cobraste por este producto, podés comprar otro hoy?"* (contra el precio de compra actual). Es el criterio que se usa en contextos de inflación.
- No se convierten pesos a dólares ni se ajusta por índice hasta tener una fuente confiable: mejor ningún dato que uno equivocado.
- Es de la etapa 9 (estadísticas). En la etapa 4 solo se **guarda el costo** en cada línea, para no perder el dato.

---

## 8. Fiados (entran en la beta ✅) y GoCuotas (⏭️ después)

| Caso | Decisión |
|---|---|
| **Fiado en venta rápida** ✅ | Se puede guardar con saldo pendiente si hay **cliente** elegido. Aparece en "Me deben" |
| **Fiado en una orden** ✅ | "Entregar debiendo": la orden se cierra con saldo pendiente, con confirmación explícita (*"Juan Pérez se lleva el equipo debiendo $8.000"*) |
| **Cobrar un fiado** ✅ | Desde "Me deben" o desde la ficha del cliente: "Cobrar $X a Juan Pérez" → entra a Efectivo o Digital |
| **GoCuotas / tarjeta diferida** ⏭️ después de la beta | El método de pago tiene "acredita en N días". El pago va a **A cobrar** con su fecha. El día que llega, el programa pregunta "¿Ya entró?" y lo pasa a Digital |

⏭️ GoCuotas queda para después (21/11/2026). Pendiente para entonces: ¿acredita el mismo monto o descuenta una comisión? Mientras tanto, una venta con GoCuotas se registra como hoy.

---

## 9. Organización del código ✅

**Problema:** la app se llama `catalogo`, pero tiene **todo** (órdenes, pagos, ventas, devoluciones) y va a tener la caja y el stock.

**Propuesta:** antes de la caja, renombrarla a **`negocio`** (✅ aprobado) y dividir sus archivos por tema:

```
negocio/
├── models/       catalogo.py · ordenes.py · pagos.py · caja.py · stock.py
├── servicios/    ordenes.py · pagos.py · caja.py · stock.py · controles.py
└── tests/        un archivo por tema
```

**Es el mejor momento:** todavía no hay datos reales. Las migraciones se rehacen desde cero y se vuelven a cargar los datos de prueba. Los 361 tests tienen que seguir pasando sin cambiar lo que prueban. Va en una rama propia y chica, antes de la caja. Las direcciones (`/catalogo/`) y lo que ve el usuario no cambian.

---

## 10. Tests

| Práctica | Cómo |
|---|---|
| Una regla por test | Patrón preparar → actuar → verificar. Nombre que diga la regla: `test_retiro_mayor_al_saldo_no_se_guarda` |
| Valores límite | $0, $0,01, saldo exacto, saldo + $0,01; stock 0, 1 y exacto |
| Todo o nada | Si un paso falla en la mitad, no queda ningún movimiento ni cambio |
| Invariantes | Saldo = suma de movimientos; Señas = pagos de órdenes abiertas; un anulado no suma; el historial no se pierde |
| **Pruebas con datos al azar** (`hypothesis`) | Secuencias largas de operaciones al azar (pagar, devolver, entregar, retirar, anular) y en cada paso se comprueban los invariantes |
| Cobertura (`coverage`, con ramas) | Objetivo: 100 % en `servicios/caja.py` y `servicios/stock.py`; el informe se revisa en cada paso |
| Pantallas | Cada botón hace lo que dice su texto; las confirmaciones aparecen; sin login no entra |

---

## 11. Orden de trabajo (cada paso con tests y una pantalla mínima para probar)

| Paso | Qué | Para probar |
|---|---|---|
| 4.0 | Rama chica: renombrar `catalogo` → `negocio` y dividir archivos (§9) | Que todo siga igual y pasen los 361 tests |
| 4.1 | Cajas, `MovimientoCaja`, historial, saldo inicial de ejemplo | Pantalla Caja mínima: saldos y movimientos |
| 4.2 | Conectar el dinero existente: pagos → Señas, entregar → pase, devoluciones, venta rápida, corregir y anular | Hacer una orden completa y verla en la caja |
| 4.3 | Retiros, gastos, compra de mercadería, pases, "Conté y hay $X" | Los botones de la caja |
| 4.4 | Stock: movimientos, "No lleva stock", bloqueo, "Corregir el stock" | Columna "Hay" y el bloqueo al vender |
| 4.5 | Fiados (en venta rápida y en órdenes) | Vender fiado, entregar debiendo y cobrarlo después |
| 4.6 | Controles automáticos y preguntas de vez en cuando | La pantalla "Revisar que todo esté bien" |
| 4.7 | Pulir las pantallas (textos de ayuda, colores, celular) | Demo con el dueño |

**Forma de trabajo en esta etapa ✅:** el código base lo escribo yo (Claude) y lo presento prolijo, explicado paso por paso, para que el desarrollador lo revise y corrija. Los commits los hace el desarrollador.

---

## 12. Datos de ejemplo (para desarrollo)

El comando de datos de prueba va a cargar, como ejemplo, saldos iniciales y stock tomados de la hoja "Stock" del Excel. Los valores reales se cargan el día de la instalación.

| Caja | Saldo inicial de ejemplo |
|---|---|
| Efectivo | $150.000 |
| Digital | $420.000 |
| Señas | $0 (se forma con las órdenes abiertas) |

---

## 13. Preguntas abiertas

| # | Pregunta | Sección |
|---|---|---|
| 1 | ¿Separar banco / Mercado Pago / Naranja X en "Más detalle"? Mientras no se decida, digital es una sola caja y "Más detalle" muestra lo que entró por cada método | §3.3 |
| 2 | GoCuotas: ¿descuenta comisión? (para después de la beta) | §8 |

Resueltas el 21/11/2026: corregir y anular con historial ✅ · reservar todo por defecto con opción de solo la reparación ✅ · productos de una orden: opción A ✅ · preguntas una vez por semana ✅ · GoCuotas después ⏭️ · nombre `negocio` ✅

> **Me gusta que me preguntes si quiero avanzar al siguiente paso o no, antes de avanzar.**
