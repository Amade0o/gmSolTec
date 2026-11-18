"""Tipos de equipo en una tabla (antes eran una lista fija en el código).

La columna "tipo" de equipos y modelos sigue guardando el mismo texto ("celular",
"notebook", "pc"): ahora apunta a TipoEquipo.clave. No se convierte ningún dato.
"""
import django.db.models.deletion
from django.db import migrations, models

TIPOS = [("celular", "Celular"), ("notebook", "Notebook"), ("pc", "PC")]


def cargar_tipos(apps, schema_editor):
    TipoEquipo = apps.get_model("catalogo", "TipoEquipo")
    for clave, nombre in TIPOS:
        TipoEquipo.objects.get_or_create(clave=clave, defaults={"nombre": nombre})
    # Si quedó algún tipo cargado que no estaba en la lista, se crea para no romper la relación
    for modelo in ("EquipoRecibido", "ModeloEquipo"):
        for clave in apps.get_model("catalogo", modelo).objects.values_list("tipo", flat=True).distinct():
            TipoEquipo.objects.get_or_create(clave=clave, defaults={"nombre": clave.capitalize()})


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0016_textos_de_estado_y_bloqueo")]

    operations = [
        migrations.CreateModel(
            name="TipoEquipo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("clave", models.SlugField(editable=False, max_length=20, unique=True)),
                ("nombre", models.CharField(max_length=40, unique=True)),
                ("activo", models.BooleanField(default=True)),
            ],
            options={"ordering": ["nombre"], "verbose_name": "tipo de equipo", "verbose_name_plural": "tipos de equipo"},
        ),
        migrations.RunPython(cargar_tipos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="equiporecibido", name="tipo",
            field=models.ForeignKey(db_column="tipo", on_delete=django.db.models.deletion.PROTECT,
                                    related_name="equipos", to="catalogo.tipoequipo", to_field="clave"),
        ),
        migrations.AlterField(
            model_name="modeloequipo", name="tipo",
            field=models.ForeignKey(db_column="tipo", limit_choices_to={"activo": True},
                                    on_delete=django.db.models.deletion.PROTECT, related_name="modelos",
                                    to="catalogo.tipoequipo", to_field="clave"),
        ),
    ]
