# Demo mínima de Django (GMSol)

Sirve solo para ver cómo se siente la tecnología. Es descartable: no es el diseño final.
Usa SQLite para no instalar nada; en el proyecto real será MySQL (se cambia en `config/settings.py`).

## Cómo correrla (necesitás Python 3.10 o más)

```
pip install django
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abrí http://127.0.0.1:8000/admin e ingresá con el usuario que creaste.

## Qué probar

1. Creá una **categoría** ("Cables") y una **marca** ("Samsung").
2. Creá un **producto**: la marca es opcional, la categoría no. Mirá la columna **margen**: se calcula, no se guarda.
3. Creá un **cliente**, el telefono es muy importante
4. Agregá dos teléfonos al mismo cliente.
5. Intentá borrar una categoría que tiene productos: está protegida.

## Dónde mirar el código

- `catalogo/models.py`: las clases y sus relaciones (son las del diagrama del módulo 1).
- `catalogo/admin.py`: las pantallas que Django arma solo.
