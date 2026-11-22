"""Carga los tipos de equipo de siempre (Celular, Notebook, PC).

Antes lo hacía la migración 0017 de la app 'catalogo'. Al renombrar la app a 'negocio' (21/11/2026)
las migraciones empezaron de cero, y esta carga se conserva como migración de datos.
"""
from django.db import migrations

TIPOS = [("celular", "Celular"), ("notebook", "Notebook"), ("pc", "PC")]


def cargar_tipos(apps, schema_editor):
    TipoEquipo = apps.get_model("negocio", "TipoEquipo")
    for clave, nombre in TIPOS:
        TipoEquipo.objects.get_or_create(clave=clave, defaults={"nombre": nombre})


class Migration(migrations.Migration):
    dependencies = [("negocio", "0001_initial")]

    operations = [migrations.RunPython(cargar_tipos, migrations.RunPython.noop)]
