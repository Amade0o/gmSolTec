# GMSol — Guía de diseño de la interfaz (v2)

> **Uso:** documento corto para cargar como contexto antes de hacer cualquier pantalla.
> **v2 (16/11/2026):** propuesta **"H2 + pista de progreso"**. Mantiene los colores y la distribución de la v1 (propuesta F), pero la v1 se veía "de juguete" (todo muy redondeado, menú flotante, pastillas de color, todo en negrita). La v2 es más sobria y toma la identidad del logo: **hexágono** y **pistas de circuito**. Implementada en `web/static/web/css/gmsol-v2.css`, que se carga encima de `gmsol.css` (sacándola se vuelve a la v1).
> **Estilo en una frase:** cálido, serio y legible. Papel crema, tinta oscura, naranja de marca usado con criterio. Redondeado, sin ángulos duros ni efectos.
> **Prioridad del desarrollador:** minimalista, nada genérico ni que parezca hecho con IA.

---

## 1. Estructura de la pantalla

| Zona | Qué lleva |
|---|---|
| **Franja superior** (crema, de lado a lado, línea fina abajo) | Logo a la izquierda, buscador, y las **tres acciones frecuentes** a la derecha: *Nueva orden* (naranja), *Venta rápida*, *Entregar equipo*. El logo va siempre sobre crema: sobre fondo oscuro no se ve bien |
| **Menú lateral** (carbón cálido, **pegado al borde**, de la franja hasta abajo, sin esquinas redondeadas) | Secciones agrupadas: *Trabajo*, *Registros*, *Próximamente*, *Cuenta*. Íconos de línea. El ítem activo lleva fondo más claro, texto `#FFD2AA` y un **hexágono naranja** chico a la derecha |
| **Contenido** | **Fecha del día** chica arriba, título, y debajo paneles. En pantallas de edición, una columna de resumen que acompaña |

**Celular (menos de 860 px):** el menú pasa a una barra horizontal que se desliza (con esquinas redondeadas, sin barra de scroll visible), los paneles se apilan y los tres conteos quedan en una fila.

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

| Estado | Texto | Marca (hexágono) | Fondo suave (solo si hace falta) |
|---|---|---|---|
| En revisión / reparación | `#6B4A00` | `#D69A1B` | `#FCEBC8` |
| Lista, saldado | `#1E5B2B` | `#3E8E52` | `#DFF0DF` |
| No arreglable, devolver | `#8A2A1C` | `#C4503C` | `#F8DAD5` |

En la v2 el estado se muestra como **hexágono de color + texto del color**, sin pastilla de fondo. Un saldo **a favor del cliente** va en el texto rojo, en negrita.

**Reglas de color**
- **Nunca texto naranja sobre fondo claro** (no se lee). El texto de acento es el cobre oscuro.
- El naranja se usa para **una sola acción principal por pantalla**.
- El blanco puro solo en campos de formulario.
- Todos los pares de texto y fondo cumplen contraste mínimo 4,5 a 1.

---

## 3. Tipografía

| Uso | Valor |
|---|---|
| Familia del texto | **Figtree** (400, 500, 600, 700), con `Segoe UI` y sans-serif de respaldo |
| Números grandes, fecha y títulos del menú | **Barlow Condensed** (600, 700). Recuerda las letras gruesas del logo. Fecha y títulos del menú en mayúscula, con espacio entre letras |
| Números de orden en tablas | **IBM Plex Mono** 500, color secundario (`#6`) |
| Texto base | 15 px. Ítems del menú y tabla 14,5 px, peso 500 |
| Título de pantalla | 28 px, 700 |
| Título de panel | 16 px, 700 |
| Etiqueta de campo | 13,5 px, 600, color secundario |
| Tabla | 14,5 px, números tabulares. Encabezados en mayúscula, 11 px. Nombre del cliente en 600. Montos alineados a la derecha |
| Números de las tarjetas de conteo | Barlow Condensed 44 px, 700 |

---

## 4. Forma y espacio

| Elemento | Valor |
|---|---|
| Radio de campos y botones | 9 px |
| Radio de paneles y tarjetas | 12 px |
| Radio de los ítems del menú | 8 px. El menú en sí no tiene radio (va pegado al borde) |
| Alto de botones y campos | **40 px** en la franja. En formularios de pantalla táctil se puede subir a 44 px |
| Alto de ítems del menú | 36 px |
| Separaciones | múltiplos de 4: 8, 12, 14, 18, 20, 24 |
| Sombras | ninguna o casi imperceptible. Se separa con bordes finos |

---

## 5. Componentes

- **Botón principal:** naranja, texto oscuro, 44 px. **Botón secundario:** fondo de panel, borde fino. **Enlace:** cobre oscuro, subrayado.
- **Estado:** hexágono de color + texto del color, 14 px, peso 500. (El chip con fondo de la v1 queda en `gmsol.css` por si hace falta.)
- **Pista de progreso** (el toque propio de la v2): el estado de una orden se dibuja como las **pistas de circuito del logo**, con cuatro nodos: *Recibida → Revisión → Lista → Entregada*. Los pasos hechos van rellenos, el paso actual es un **hexágono** y lo que falta es un círculo vacío. Toma el color del estado (no arreglable: queda en el tercer paso, en rojo). **Siempre va acompañada del texto del estado**: no hay que aprender a leerla. Es decorativa para lectores de pantalla (`aria-hidden`). Se calcula con el filtro `pista` de `web/templatetags/formato.py`, no se guarda nada.
- **Tarjeta de conteo:** número grande en Barlow Condensed y debajo la etiqueta con su hexágono de color.
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
9. **La identidad sale del logo** (hexágono, pistas de circuito, letra gruesa) y se usa con medida: marcas chicas, nunca como decoración de fondo.

---

## 7. Logo

| Fondo | Versión |
|---|---|
| Crema (franja superior, impresión) | Logo completo con fondo transparente |
| Oscuro | Logo invertido: contorno y letras crema, naranja igual. **Evitarlo en la interfaz:** se probó en el menú oscuro y no se ve bien |

- Alto en la franja: 42 px (escritorio) y 40 px (celular).
- No se recolorea, no se estira y no se pone sobre un recuadro blanco.

---

## 8. Cómo se implementa

- **Django + plantillas + HTMX**, con **CSS propio** (sin Bootstrap ni Tailwind). Los valores de esta guía van como variables CSS.
- **Dos archivos:** `gmsol.css` (base v1) y `gmsol-v2.css` (lo que cambia en la v2). Lo nuevo va en `gmsol-v2.css`.
- Tipografías por enlace a Google Fonts (Figtree, Barlow Condensed, IBM Plex Mono). Pasan a archivos locales en la etapa 12.
- **JavaScript** solo para el cálculo en vivo y el patrón de bloqueo.
- Las pantallas se construyen en este orden: inicio, nueva orden, lista de órdenes, detalle de orden (cerrar y devolver), venta rápida, entregar.
