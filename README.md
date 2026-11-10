# gmSolTec

Aplicación web de **GMSolucionesTecnologicas**. Actualmente el repositorio
contiene una demo de Django en [`gmsol_demo/`](./gmsol_demo/).

- Para una vista general y el flujo completo, usar este archivo.
- Para trabajar dentro de la demo, consultar
  [`gmsol_demo/LEEME.md`](./gmsol_demo/LEEME.md).

## Requisitos

- Python 3.12 o superior.
- `pip`.

El proyecto usa Django 6.1.1 y SQLite. No hay un `requirements.txt` todavía,
por lo que la dependencia se instala explícitamente.

## Instalación

Los siguientes comandos se ejecutan desde la raíz del repositorio:

```bash
cd gmsol_demo
python3 -m venv .venv
source .venv/bin/activate       # Linux/macOS
python -m pip install --upgrade pip
python -m pip install Django==6.1.1
```

En Windows PowerShell, activar el entorno con:

```powershell
.\.venv\Scripts\Activate.ps1
```

Cada vez que se abra una terminal nueva hay que volver a activar el entorno:

```bash
cd gmsol_demo
source .venv/bin/activate
```

## Comandos de Django

Ejecutar estos comandos desde `gmsol_demo/`, con el entorno virtual activado:

```bash
# Comprobar la configuración
python manage.py check

# Crear y aplicar cambios de base de datos
python manage.py makemigrations
python manage.py migrate

# Ver el estado de las migraciones
python manage.py showmigrations

# Crear el usuario administrador
python manage.py createsuperuser

# Iniciar el servidor de desarrollo
python manage.py runserver
```

Abrir <http://127.0.0.1:8000/admin/> e iniciar sesión con el superusuario.
`runserver` se puede detener con `Ctrl+C`.

Para abrir una consola interactiva con el proyecto configurado:

```bash
python manage.py shell
```

## Tests

Ejecutar toda la suite:

```bash
python manage.py test
```

Ejecutar cada etapa por separado:

```bash
python manage.py test catalogo.tests.test_etapa1
python manage.py test catalogo.tests.test_etapa2
python manage.py test catalogo.tests.test_etapa3_correcciones
python manage.py test catalogo.tests.test_etapa3_cierre_orden
python manage.py test catalogo.tests.test_etapa3_pagos
python manage.py test catalogo.tests.test_etapa3_devoluciones
python manage.py test catalogo.tests.test_etapa3_venta_directa
python manage.py test catalogo.tests.test_etapa3_reporte_manual
```

Para ejecutar un único test, agregar el nombre de la clase y del método:

```bash
python manage.py test catalogo.tests.test_etapa1.ProductoTests.test_margen_se_calcula_con_los_dos_precios
```

Django crea una base de datos temporal para los tests; no se modifica
`gmsol_demo/db.sqlite3`.

## Datos de prueba

El comando propio carga marcas, modelos, categorías, productos, reparaciones,
métodos de pago y clientes:

```bash
python manage.py cargar_datos_prueba
```

Se puede ejecutar varias veces: usa `get_or_create` y está pensado para no
duplicar los datos que ya existen.

