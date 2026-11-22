# Demo mínima de Django (GMSol)

Esta carpeta contiene la demo funcional de gmSolTec. Es un proyecto Django
con SQLite (la misma base que se usa en el local). El README principal del repositorio está en
[`../README.md`](../README.md); este archivo concentra los comandos que se
ejecutan dentro de `gmsol_demo/`.

## Instalación

Requiere Python 3.12 o superior. Desde la raíz del repositorio:

```bash
cd gmsol_demo
python3 -m venv .venv
source .venv/bin/activate       # Linux/macOS
python -m pip install --upgrade pip
python -m pip install Django==6.1.1
```

En Windows PowerShell:

```powershell
cd gmsol_demo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install Django==6.1.1
```

Si ya existe el entorno virtual, solamente hay que activarlo:

```bash
cd gmsol_demo
source .venv/bin/activate
```

## Preparar y ejecutar la demo

Todos los comandos siguientes se ejecutan desde `gmsol_demo/`:

```bash
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abrir <http://127.0.0.1:8000/> (la interfaz del local) e ingresar con el usuario creado.
El admin queda en <http://127.0.0.1:8000/admin/> para correcciones puntuales.
Detener el servidor con `Ctrl+C`.

Cuando se cambien modelos, crear y aplicar migraciones con:

```bash
python manage.py makemigrations
python manage.py migrate
```

Otros comandos útiles:

```bash
python manage.py showmigrations
python manage.py shell
```

## Cargar datos de prueba

El comando propio carga datos iniciales de catálogo, reparaciones, métodos de
pago y clientes:

```bash
python manage.py cargar_datos_prueba
```

Es seguro ejecutarlo más de una vez: no duplica los registros que administra.

## Ejecutar tests

Suite completa:

```bash
python manage.py test
```

Por archivo:

```bash
python manage.py test catalogo.tests.test_etapa1
python manage.py test catalogo.tests.test_etapa2
python manage.py test catalogo.tests.test_etapa3_correcciones
python manage.py test catalogo.tests.test_etapa3_cierre_orden
python manage.py test catalogo.tests.test_etapa3_pagos
python manage.py test catalogo.tests.test_etapa3_devoluciones
python manage.py test catalogo.tests.test_etapa3_venta_directa
python manage.py test catalogo.tests.test_etapa3_reporte_manual
python manage.py test catalogo.tests.test_etapa7_servicios
python manage.py test web          # todas las pantallas
```

Ejemplo de un único test:

```bash
python manage.py test catalogo.tests.test_etapa1.ProductoTests.test_margen_se_calcula_con_los_dos_precios
```

Los tests usan una base de datos temporal y no deberían alterar
`db.sqlite3`.

## Qué probar manualmente

1. Crear una **categoría** (`Cables`) y una **marca** (`Samsung`).
2. Crear un **producto**: la marca es opcional y la categoría obligatoria.
   La columna **margen** se calcula, no se guarda.
3. Crear un **cliente** y agregarle dos teléfonos.
4. Intentar borrar una categoría que tiene productos: la relación está
   protegida.
5. Ejecutar `cargar_datos_prueba` y revisar los registros desde el admin.

## Dónde mirar el código

- [`catalogo/models.py`](./catalogo/models.py): clases y relaciones.
- [`catalogo/admin.py`](./catalogo/admin.py): pantallas del admin.
- [`catalogo/servicios.py`](./catalogo/servicios.py): reglas de negocio.
- [`catalogo/management/commands/cargar_datos_prueba.py`](./catalogo/management/commands/cargar_datos_prueba.py):
  datos iniciales.
- [`catalogo/tests/`](./catalogo/tests/): tests automatizados.
- [`config/settings.py`](./config/settings.py): configuración y base SQLite.
