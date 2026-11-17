"""{% estatico 'web/css/gmsol.css' %} → /static/web/css/gmsol.css?v=1763338000

Como {% static %}, pero le agrega la fecha de modificación del archivo. Cuando el
archivo cambia, cambia la dirección, y el navegador lo vuelve a bajar en vez de usar
el viejo que tenía guardado (con F5 común, Chrome reusa el CSS y el JS de la caché:
HTML nuevo con CSS viejo = pantalla rota).
"""
import os
from functools import lru_cache

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


def _version(ruta):
    archivo = finders.find(ruta)
    return int(os.path.getmtime(archivo)) if archivo else 0


_version_guardada = lru_cache(maxsize=None)(_version)   # fuera de DEBUG los archivos no cambian


@register.simple_tag
def estatico(ruta):
    version = _version(ruta) if settings.DEBUG else _version_guardada(ruta)
    return f"{static(ruta)}?v={version}"
