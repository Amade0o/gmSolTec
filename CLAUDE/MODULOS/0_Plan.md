# GMSol — Etapas del proyecto (v1)

> **Uso:** hoja de ruta breve para cargar como contexto. El orden puede cambiar a medida que avancemos.
> **Leyenda:** ✅ cerrada · 🔄 en curso · ⬜ pendiente

---

## Forma de trabajar en cada etapa

```
Charla y decisiones → .md de diseño → código (lo escribe el desarrollador) → tests → merge a main
```

- Pasos chicos, con explicación de flujos y tecnologías.
- Una rama de Git por etapa, creada **desde `main`**, y se mergea cuando los tests pasan.

---

## Etapas

| # | Etapa | Qué incluye | Estado |
|---|---|---|---|
| 0 | Requisitos y análisis | Consigna, casos, modelo BPMN v2, stack y arquitectura (Django, MySQL, servidor local, backups en Drive) | ✅ |
| 1 | **Catálogo** | Clientes y teléfonos, productos y categorías, marcas, modelos de equipo, reparaciones y sus categorías. 27 tests | ✅ *(falta en código: `Producto.codigo`, `Proveedor`, `Configuracion`)* |
| 2 | **Orden de trabajo** | Orden, equipos recibidos, líneas de reparación y de producto, estado de la orden calculado. 38 tests | ✅ *(falta: historial de estados)* |
| 3 | **Pagos y ventas** | Métodos de pago y recargos, seña y saldo, venta (Factura C para ARCA), un pago registrado y otro no, venta directa, devoluciones | ⬜ siguiente |
| 4 | **Caja y movimientos** | Efectivo y transferencia, movimientos de caja y de stock, todo en una sola transacción al registrar la venta | ⬜ |
| 5 | **Compras y proveedores** | Compras, pagos a proveedores, cuenta corriente, stock entrante | ⬜ |
| 6 | **Reglas de negocio** | Capa propia, separada de los modelos: transiciones de estado, registrar venta, recargos (patrones *State* y *Strategy*) | ⬜ |
| 7 | **Pantallas propias** | Orden en una sola pantalla, ventas, pagos, caja; login (Django + HTMX) | ⬜ |
| 8 | **Integración con ARCA** | Facturación electrónica, opción de facturar o no cada transferencia | ⬜ |
| 9 | **Estadísticas** | Por fechas, marcas, modelos, reparaciones, proveedores y clientes | ⬜ |
| 10 | **Impresión de la orden** | PDF de dos partes (empleado y cliente, con aviso de 30 días) | ⬜ |
| 11 | **Datos iniciales y migración** | Categorías genéricas, "Revisión / diagnóstico", importar los Excel | ⬜ |
| 12 | **Instalación y backups** | PC del negocio, MySQL, servidor, backups cifrados a Drive, script de actualización, quitar el nombre "demo" | ⬜ |
| 13 | **Prueba con el dueño y ajustes** | Uso real, correcciones, cierre | ⬜ |

---

> **Me gusta que me preguntes si quiero avanzar al siguiente paso o no, antes de avanzar.**
