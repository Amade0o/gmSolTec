# GMSol — Guía de diseño de la interfaz (v1)

> **Uso:** documento corto para cargar como contexto antes de hacer cualquier pantalla. Se basa en la propuesta **F** del lienzo de diseño (menú lateral carbón flotante, logo en franja crema).
> **Estilo en una frase:** cálido, serio y legible. Papel crema, tinta oscura, naranja de marca usado con criterio. Redondeado, sin ángulos duros ni efectos.
> **Prioridad del desarrollador:** minimalista, nada genérico ni que parezca hecho con IA.

---

## 1. Estructura de la pantalla

| Zona | Qué lleva |
|---|---|
| **Franja superior** (crema) | Logo a la izquierda, buscador, y las **tres acciones frecuentes** a la derecha: *Nueva orden* (naranja), *Venta rápida*, *Entregar equipo* |
| **Menú lateral** (carbón cálido, panel flotante con esquinas redondeadas) | Secciones agrupadas: *Trabajo*, *Registros*, *Próximamente*. El ítem activo se marca con un fondo más claro |
| **Contenido** | Título, y debajo paneles. En pantallas de edición, una columna de resumen que acompaña |

**Celular (menos de 860 px):** el menú pasa a una barra horizontal que se desliza, y los paneles se apilan en una columna.

---

## 2. Color

| Uso | Valor |
|---|---|
| Fondo de la app | `#F6F1E7` (crema) |
| Paneles | `#FDFBF6` |
| Líneas y bordes | `#E0D6C3` |
| Texto | `#2B2420` |
| Texto secundario | `#6A5F55` |
| **Botón principal** | Fondo `#F08030` (naranja del logo) con texto **`#201818`** |
| **Acento de texto, enlaces y foco** | `#A64A00` (cobre oscuro) |
| Menú lateral | Fondo `#3A302B`, texto `#F1E9DD`, secundario `#C2B5A6`, ítem activo `#54402F` con texto `#FFD2AA` |
| Campos de formulario | Fondo `#FFFFFF`, borde `#CDBFA8` |

**Estados** (siempre con texto, nunca solo color):

| Estado | Fondo | Texto | Punto |
|---|---|---|---|
| En revisión / reparación | `#FCEBC8` | `#6B4A00` | `#D69A1B` |
| Lista, saldado | `#DFF0DF` | `#1E5B2B` | `#3E8E52` |
| No arreglable, devolver | `#F8DAD5` | `#8A2A1C` | `#C4503C` |

**Reglas de color**
- **Nunca texto naranja sobre fondo claro** (no se lee). El texto de acento es el cobre oscuro.
- El naranja se usa para **una sola acción principal por pantalla**.
- El blanco puro solo en campos de formulario.
- Todos los pares de texto y fondo cumplen contraste mínimo 4,5 a 1.

---

## 3. Tipografía

| Uso | Valor |
|---|---|
| Familia | **Figtree** (400, 600, 700), con `Segoe UI` y sans-serif de respaldo |
| Texto base | 16 px |
| Título de pantalla | 28 px, 700 |
| Título de panel | 19 px, 700 |
| Subtítulo dentro de un panel | 16 px, 700 |
| Etiqueta de campo | 13,5 px, 600, color secundario |
| Tabla | 15,5 px. Encabezados en mayúscula, 12,5 px |

---

## 4. Forma y espacio

| Elemento | Valor |
|---|---|
| Radio de campos y botones | 10 px |
| Radio de paneles | 14 px |
| Radio del menú flotante | 18 px |
| Chips | totalmente redondeados |
| Alto mínimo de botones y campos | **44 px** |
| Separaciones | múltiplos de 4: 8, 12, 14, 18, 20, 24 |
| Sombras | ninguna o casi imperceptible. Se separa con bordes finos |

---

## 5. Componentes

- **Botón principal:** naranja, texto oscuro, 44 px. **Botón secundario:** fondo de panel, borde fino. **Enlace:** cobre oscuro, subrayado.
- **Chip de estado:** fondo suave, texto oscuro, 13,5 px.
- **Panel:** fondo de panel, borde fino, radio 14 px, título arriba. Los pasos de un formulario llevan un número en círculo carbón.
- **Campo de solo lectura:** fondo crema oscuro, valor en negrita (para valores calculados).
- **Selector de opciones corto** (tipo de bloqueo): control segmentado, con la opción activa en carbón.
- **Patrón de bloqueo:** cuadrícula de 9 puntos que se toca en orden, con la línea en cobre. Guarda la secuencia como `1-5-9-6`.
- **Saldo:** siempre en palabras y en un cuadro destacado: `Debe $X`, `A favor del cliente: $X (se debe devolver)` o `Saldado`.

---

## 6. Reglas de interfaz (decisiones del dueño)

1. **Primero qué se vende o se repara, después el precio.** En todos los formularios, el orden de carga es reparación o producto → cantidad → precio.
2. El **número de la orden** se ve siempre al editar cualquier cosa de esa orden (título y migas de pan). En una orden nueva dice que se asigna al guardar.
3. Los **totales se calculan al vuelo**, sin tener que apretar guardar.
4. Un equipo **nuevo** siempre empieza como *En revisión / reparación*. El resultado se carga después.
5. Las acciones frecuentes están siempre en la franja superior.
6. **Registrar que hay que devolver** y **marcar que ya se devolvió** son dos acciones distintas, en dos lugares distintos.
7. Los números negativos nunca se muestran solos: se traducen a palabras.
8. Sin emojis ni íconos decorativos. Íconos de línea simple solo en el menú.

---

## 7. Logo

| Fondo | Versión |
|---|---|
| Crema (franja superior, impresión) | Logo completo con fondo transparente |
| Oscuro | Logo invertido: contorno y letras crema, naranja igual |

- Alto mínimo: 40 px (celular) y 50 px (escritorio).
- No se recolorea, no se estira y no se pone sobre un recuadro blanco.

---

## 8. Cómo se implementa

- **Django + plantillas + HTMX**, con **CSS propio** (sin Bootstrap ni Tailwind). Los valores de esta guía van como variables CSS.
- **JavaScript** solo para el cálculo en vivo y el patrón de bloqueo.
- Las pantallas se construyen en este orden: inicio, nueva orden, lista de órdenes, detalle de orden (cerrar y devolver), venta rápida, entregar.
