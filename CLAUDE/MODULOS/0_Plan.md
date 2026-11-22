# GMSol — Plan del proyecto (v3)

> **Uso:** hoja de ruta corta para cargar como contexto. Los detalles de cada etapa están en sus propios `.md`.
> **Estado al 21/11/2026:** etapas 1, 2, 3 y casi toda la 7 terminadas, 361 tests pasando. **Lo próximo: la demo y la etapa 4 (diseño en revisión).** Los fiados (antes 3b) pasan a la beta; GoCuotas queda para después.
> **Vocabulario:** **Venta** = registro interno que cierra una transacción e impacta stock y caja. **Comprobante ARCA** = documento legal (etapa 8).
> **Leyenda:** ✅ hecho · 🔄 en curso · ⬜ pendiente · ⏭️ después de la versión final

---

## 1. Los tres hitos

| Hito | Cuándo | Qué tiene | Datos | Para qué |
|---|---|---|---|---|
| 🎬 **Demo** | **Ahora** (no hay que programar nada más) | Todas las pantallas de órdenes, ventas, devoluciones, clientes, productos y configuración | De prueba (`cargar_datos_prueba`) | Que el dueño la use con casos concretos, ver dónde duda y relevar cómo maneja la caja, el stock y los fiados |
| 🧪 **Beta** | Al terminar las etapas 4, 10, 11 y 12 | Lo de la demo + caja, stock, fiados, impresión, sus datos reales y backups | **Reales**, en paralelo al Excel | Usarla en el día a día sin dejar el Excel. Conviene que dure poco (2 a 4 semanas): cargar todo dos veces cansa |
| 🚀 **Versión final** | Al cerrar los ajustes de la beta (etapa 13) | Lo de la beta, corregido y sin el nombre "demo" | Reales | Deja el Excel. Lo que falta (ARCA, compras, estadísticas) llega como actualizaciones |

**La demo se hace en su PC con Windows**, no en la tuya: sirve también como ensayo de la instalación (Python, impresora, navegador). Al terminar se borra o se deja con datos de prueba, avisándole que no cargue nada real.

---

## 2. Etapas, en el orden en que se hacen

| Hito | # | Etapa | Qué incluye | Estado |
|---|---|---|---|---|
| Demo | 0 | Requisitos y análisis | Consigna, BPMN, stack (Django, SQLite, Windows) | ✅ |
| | 1 | Catálogo | Clientes y teléfonos, productos, marcas, modelos, reparaciones | ✅ |
| | 2 | Orden de trabajo | Orden, equipos, líneas de reparación y de producto, estado calculado | ✅ |
| | 3 | Pagos y ventas | Métodos de pago y recargos, pagos parciales, ventas, devoluciones | ✅ |
| | 7 | Pantallas propias | Pasos 7.0 a 7.8 (ver [etapa-7-interfaz.md](../DISEÑO/etapa-7-interfaz.md)). Faltan caja y stock | 🔄 |
| Beta | 4 | **Caja, stock y fiados** 👈 | Cajas de efectivo, digital y señas; movimientos de caja y de stock; retiros, gastos y compra de mercadería; corregir y anular con historial; controles automáticos. Diseño en [etapa-4-caja.md](../DISEÑO/etapa-4-caja.md). Antes: renombrar la app `catalogo` (paso 4.0). Fuentes: mirar [Registro.xlsx](../NOTAS_PERSONALES/Registro.xlsx), [notas_respecto_a_pagos.txt](../NOTAS_PERSONALES/notas_respecto_a_pagos.txt) y lo que surja de la demo | ⬜ |
| | 7 | Pantallas de caja y stock | Junto con la etapa 4 | ⬜ |
| | 10 | Impresión | Ya imprime la orden y el comprobante desde el navegador. Falta: texto real de las condiciones, "Guardar e imprimir", probar en su impresora | 🔄 |
| | 11 | Datos iniciales y migración | Su catálogo y precios desde los Excel (script de importación). El stock y los saldos iniciales se cargan a mano el día de la instalación | ⬜ |
| | 12 | Instalación y backups | Ver la sección 4 | ⬜ |
| Final | 13 | Ajustes de la beta | Correcciones del uso real | ⬜ |
| Después | 3b | GoCuotas y tarjeta diferida | Caja "A cobrar" con fecha de acreditación (ver [etapa-4-caja.md](../DISEÑO/etapa-4-caja.md) §8) | ⏭️ |
| | 5 | Compras y proveedores | Proveedores, cuenta corriente y estadísticas de compras. Lo mínimo (pagar mercadería y que entre al stock) va en la etapa 4 | ⏭️ |
| | 6 | Reglas de negocio | Patrones *State* y *Strategy*. Para la beta alcanza con `servicios.py` | ⏭️ |
| | 8 | ARCA | Comprobante ARCA, opción de facturar o no cada pago digital. Hasta entonces factura a mano | ⏭️ |
| | 9 | Estadísticas | Por fechas, marcas, modelos, reparaciones, proveedores y clientes | ⏭️ |

**Forma de trabajar:** charla y decisiones → `.md` de diseño → código (lo escribe el desarrollador, guiado; en la etapa 4, Claude escribe la base y el desarrollador la revisa) → tests → merge a `main`. Una rama por etapa, creada desde `main`; un commit por paso; se mergea al cerrar la etapa con los tests pasando. **Una demo corta al dueño al cerrar cada etapa.**

---

## 3. Decisiones y deuda

**Decisiones de pagos (etapa 3):**
- El estado del dinero (retenido, pendiente, disponible) **se calcula**, no se guarda.
- `Pago.monto` es lo que entra al negocio; `total_cobrado` = monto + recargo. El recargo es una copia editable del método de pago.
- Efectivo y digital son **dos cuentas de la caja**, no un "retiro" como en el Excel.
- Las devoluciones van en dos pasos (hay que devolver / ya se devolvió) y son del precio sin recargo.

**Deuda abierta:**

| # | Pendiente | Cuándo |
|---|---|---|
| 1 | Reglas de transición entre estados; ¿"esperando repuesto"? | Etapa 6 |
| 2 | Historial de estados del equipo | Etapa 6 |
| 3 | Costo del repuesto en cada reparación (ganancia) | Etapa 9 |
| 4 | `Producto.codigo`, `Configuracion` | Sin fecha |
| 5 | Etiqueta del teléfono | Sin fecha |
| 6 | Stock insuficiente al registrar la venta: ✅ no se vende, con botón "Corregir el stock" | **Etapa 4** |
| 7 | Reglas de cantidad y precio en la base de datos (hoy son validadores de Django) | Sin fecha |
| 8 | Margen por categoría | Futuro |

---

## 4. Cómo se le entrega al cliente (Windows)

Todo gratis, en su PC, sin depender de internet. Detalle técnico en [stack_tecnologico.md](../DISEÑO/stack_tecnologico.md) §9. El dueño solo ve un acceso directo que abre el navegador.

| Pieza | Herramienta | Detalle |
|---|---|---|
| Lenguaje | **Python 3.12** (instalador de python.org, con "Add to PATH") | Django 6.1 lo necesita |
| El programa | **Git para Windows** + clonar el repositorio de GitHub | Así las actualizaciones son un `git pull`. Si el repo es privado, con un token de solo lectura |
| Dependencias | `requirements.txt` (hay que crearlo): Django, Waitress, WhiteNoise | Instaladas en un `venv` dentro de la carpeta |
| Servidor | **Waitress** en `127.0.0.1:8000` | El servidor de producción para Windows; `runserver` es solo para desarrollo |
| Archivos estáticos | **WhiteNoise** + `collectstatic` | Sin DEBUG, Django no los sirve. Las tipografías ya son locales |
| Arranque | **Programador de tareas de Windows**: al iniciar sesión corre `iniciar.bat`, sin ventana | Más un **acceso directo "GMSol"** en el escritorio que abre `http://localhost:8000` |
| Configuración | Variables de entorno: `GMSOL_DEBUG=0`, `GMSOL_SECRET_KEY`, `GMSOL_HOSTS=localhost,127.0.0.1`, `GMSOL_SSL_REDIRECT=0` | Hay que hacer configurable la cookie segura: sin HTTPS, entrar desde el celular por la red del local no andaría |
| Base de datos | **SQLite** ✅ (decidido el 21/11/2026) | Un solo usuario, nada extra que instalar en Windows, la base es un archivo. La misma que ya se usa en desarrollo |
| Backups | Comando propio `respaldar`, todos los días con el Programador de tareas | Copia la base con la API de backup de SQLite, la comprime y **cifra con 7-Zip (AES-256)** y la guarda en un **USB o un segundo disco**. Guarda 30 diarios y 12 mensuales. **Probar una restauración antes de la beta**. Subirla a Google Drive: más adelante, si se quiere |
| Actualizaciones | `actualizar.bat` | Hace un backup → `git pull` → instala dependencias → `migrate` → `collectstatic` → reinicia Waitress. Lo corrés vos |

**Pasos para la instalación de la beta:**
1. Instalar Python, Git y 7-Zip; clonar el repo; crear el `venv` e instalar `requirements.txt`.
2. Definir las variables de entorno, correr `migrate`, `collectstatic` y `createsuperuser`.
3. Importar sus Excel (etapa 11).
4. Crear las tareas programadas (arranque y backup) y el acceso directo.
5. Reiniciar la PC y comprobar que arranca sola, imprime y hace el backup.
6. Hacer una restauración de prueba desde el USB.

**Para la versión final:** renombrar `gmsol_demo` y quitar "demo" de la interfaz, cambiar el texto de ejemplo de las condiciones por el real y dejar escrito (en una hoja impresa) qué hacer si la PC se rompe.

---

## Documentos

- Diseño: [stack_tecnologico.md](../DISEÑO/stack_tecnologico.md) · [etapa-4-caja.md](../DISEÑO/etapa-4-caja.md) · [etapa-7-interfaz.md](../DISEÑO/etapa-7-interfaz.md) · [casos_puntuales_diseño.md](../DISEÑO/casos_puntuales_diseño.md)
- Modelo: [BPMN.md](../BPMN%20Y%20MODELO/BPMN.md) · [notas_extra_bpmn.md](../BPMN%20Y%20MODELO/notas_extra_bpmn.md) · [guia-de-diseno-gmsol.md](../BPMN%20Y%20MODELO/guia-de-diseno-gmsol.md)
- Clases: [v6 (vigente)](diagrama-clases-modulos-1-a-3-v6.md) · [v5](diagrama-clases-modulos-1-a-3-v5.md) · [v4](diagrama-clases-modulo1y2-orden.md) · [catálogo](diagrama-clases-modulo1-catalogo.md)
- Notas del dueño: [consigna.md](../NOTAS_PERSONALES/consigna.md)

---

> **Me gusta que me preguntes si quiero avanzar al siguiente paso o no, antes de avanzar.**
