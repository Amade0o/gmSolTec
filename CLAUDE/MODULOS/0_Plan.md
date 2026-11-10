# GMSol — Etapas del proyecto (v2)

> **Uso:** hoja de ruta breve para cargar como contexto. El orden puede cambiar a medida que avancemos.
> **Leyenda:** ✅ cerrada · 🔄 en curso · ⬜ pendiente
> **Vocabulario:** **Venta** = registro interno que cierra una transacción e impacta stock y caja (antes se llamaba "factura"). **Comprobante ARCA** = documento legal, es otra cosa (etapa 8).

---

## Forma de trabajar en cada etapa

```
Charla y decisiones → .md de diseño → código (lo escribe el desarrollador, guiado) → tests → merge a main
```

- Pasos chicos pero con avance real, con explicación de flujos y tecnologías.
- Una rama de Git por etapa, creada **desde `main`**. Dentro de la etapa se hace un commit por paso o fase; **se mergea a `main` al cerrar toda la etapa**, con los tests pasando.
- No se versionan `venv/` ni `__pycache__/` (van en el `.gitignore`).
- El desarrollador pasa el código completo en cada avance y se revisa.

---

## Etapas

| # | Etapa | Qué incluye | Estado |
|---|---|---|---|
| 0 | Requisitos y análisis | Consigna, casos, modelo BPMN v2, stack y arquitectura (Django, MySQL, servidor local, backups en Drive) | ✅ |
| 1 | **Catálogo** | Clientes y teléfonos, productos y categorías, marcas, modelos de equipo, reparaciones y sus categorías | ✅ *(deuda: ver abajo)* |
| 2 | **Orden de trabajo** | Orden, equipos recibidos, líneas de reparación y de producto, estado de la orden calculado | ✅ *(deuda: ver abajo)* |
| 3 | **Pagos y ventas** | Fases 1, 2 y 5: métodos de pago y recargos, pagos parciales, ventas (cierre de orden y venta directa) y devoluciones | ✅ |
| 3b | **Fiados y pagos diferidos** | Fase 3 (fiados: venta directa con saldo pendiente) y Fase 4 (GoCuotas, tarjeta diferida) | ⏭️ después de la beta |
| 4 | **Caja y movimientos** | Efectivo y digital como cuentas, movimientos de caja y de stock, retiros del dueño, todo en una sola transacción al registrar la venta. Stock disponible = físico − reservado en órdenes abiertas | ⬜ |
| 5 | **Compras y proveedores** | Compras, pagos a proveedores, cuenta corriente, stock entrante | ⬜ |
| 6 | **Reglas de negocio** | Capa propia, separada de los modelos: transiciones de estado, cierre de venta, recargos (patrones *State* y *Strategy*) | ⬜ |
| 7 | **Pantallas propias** | Se adelanta: va **antes** de la etapa 4. Primero se define el diseño (minimalista, nada genérico), después orden en una sola pantalla, ventas, pagos y devoluciones; más adelante caja y stock. Login (Django + HTMX) | ⏭️ siguiente |
| 8 | **Integración con ARCA** | Comprobante ARCA, `facturar_arca` en cada pago (opción de facturar o no cada transferencia) | ⬜ |
| 9 | **Estadísticas** | Por fechas, marcas, modelos, reparaciones, proveedores y clientes | ⬜ |
| 10 | **Impresión de la orden** | PDF de dos partes (empleado y cliente, con aviso de 30 días) | ⬜ |
| 11 | **Datos iniciales y migración** | Categorías genéricas, "Revisión / diagnóstico", métodos de pago iniciales, importar los Excel | ⬜ |
| 12 | **Instalación y backups** | PC del negocio, MySQL, servidor, backups cifrados a Drive, script de actualización, quitar el nombre "demo" | ⬜ |
| 13 | **Prueba con el dueño y ajustes** | Uso real, correcciones, cierre | ⬜ |

---

## Camino a la beta

**Beta** = versión que el dueño puede usar **en paralelo a su Excel**.

| Etapa | ¿En la beta? | Motivo |
|---|---|---|
| 3. Pagos y ventas | ✅ Hecha | Los fiados y GoCuotas pasaron a la etapa 3b, después de la beta |
| 4. Caja y movimientos | ✅ | Es lo que reemplaza al Excel |
| 6. Reglas de negocio | 🟡 Lo mínimo | Lo que ya está en `servicios.py` alcanza; el refactor con patrones puede esperar |
| 7. Pantallas propias | ✅ | La parte más grande: orden en una pantalla, PIN visual, totales en vivo |
| 10. Impresión de la orden | ✅ | El papel de dos partes es parte de su rutina |
| 11. Datos iniciales y migración | ✅ | Su catálogo real y sus precios |
| 12. Instalación y backups | ✅ | Sin backups no se usan datos reales |
| 5. Compras, 8. ARCA, 9. Estadísticas | ⏭️ Después | Sigue facturando a mano en ARCA; el stock inicial entra con la migración |

```
Etapa 3 ✅ → Etapa 7 (interfaz: diseño y pantallas de órdenes) → Etapa 4 → resto de la etapa 7 → Etapas 10, 11 y 12 → 🎉 Beta → Etapa 13
```

---

## Etapa 3 — Fases

**Idea central:** cada pago tiene dos datos independientes. *Por dónde entró* (efectivo / digital) y *estado del dinero* (🔒 retenido · ⏳ pendiente de acreditar · ✅ disponible).

| Fase | Qué se construye | Resuelve | Estado |
|---|---|---|---|
| 0 | Vocabulario y decisiones | "Factura" → **Venta** | ✅ |
| 1 | `MetodoPago` + `Pago` ligado a la orden. Propiedades de la orden: `total`, `monto_pagado`, `monto_adeudado`, `adeuda` | Seña, saldo, métodos distintos, recargo | ✅ |
| 2 | **Venta**: cierre de orden (`cerrar_orden`) y venta directa (`vender_directo`). `Pago.retenido` y `monto_retenido` | Retiro: 🔒 → ✅, venta sin orden | ✅ |
| 3 | Saldo pendiente de productos | Fiados | ⏭️ etapa 3b |
| 4 | Pagos ⏳ con fecha de acreditación | GoCuotas, tarjeta diferida | ⏭️ etapa 3b |
| 5 | Devoluciones | Equipo no arreglable, orden mixta, devolver una reparación completa, estado `finalizada` | ✅ |

**Decisiones tomadas:**
- El estado del dinero (retenido, etc.) **se calcula**, no se guarda.
- `Pago.recargo_porcentaje` es una **copia editable** de `MetodoPago.recargo_porcentaje` (queda como foto del momento).
- `Pago.monto` es lo que ingresa al negocio; `total_cobrado` = monto + recargo (lo que paga el cliente).
- `Pago.orden_trabajo` es opcional (venta directa).
- Efectivo y digital son **dos cuentas de la caja**, no un "retiro" como en el Excel del dueño.
- `facturar_arca` queda para la etapa 8.
- Las devoluciones se registran en dos pasos (hay que devolver / ya se devolvió); un equipo nuevo siempre empieza en revisión.

---

## Deuda de las etapas 1 y 2

| # | Pendiente | Se resuelve en |
|---|---|---|
| 1 | Estados de la orden y transiciones (¿volver de `arreglado` a `pendiente`? ¿"esperando repuesto"?) | Fase 2 de la etapa 3 y etapa 6 |
| 2 | Historial de estados del equipo (tabla que solo se agrega) | Etapa 6 |
| 3 | Costo del repuesto en cada línea de reparación (ganancia) | Etapa 9 o antes |
| 4 | `Producto.codigo`, `Proveedor`, `Configuracion` | `Proveedor`: etapa 5. Resto: pendiente de fecha |
| 5 | Teléfono: etiqueta y un solo principal. `Cliente.codigo`: ¿se mantiene? | Pendiente |
| 6 | Stock insuficiente al registrar la venta | Etapa 4 |
| 7 | Reglas de cantidad y precio blindadas en la base de datos | Pendiente |
| 8 | Margen por categoría | Futuro |
| 9 | ~~Orden con equipos mezclados (uno no arreglable): sus líneas no deberían cobrarse~~ | ✅ Resuelto en la Fase 5 |

---

> **Me gusta que me preguntes si quiero avanzar al siguiente paso o no, antes de avanzar.**
