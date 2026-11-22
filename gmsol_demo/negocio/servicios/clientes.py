"""Servicios de clientes y teléfonos.

Regla: un cliente con teléfonos tiene exactamente uno principal.
"""
from django.db import transaction
from django.db.models import ProtectedError

from ..models import Telefono
from .comun import ReglaDeNegocioError


@transaction.atomic
def crear_cliente(cliente, telefono=""):
    """Guarda un Cliente nuevo (sin guardar) y, si viene, su teléfono como principal."""
    cliente.full_clean()
    cliente.save()
    if telefono:
        agregar_telefono(cliente, telefono)
    return cliente


@transaction.atomic
def agregar_telefono(cliente, numero, principal=False):
    """El primer teléfono del cliente queda como principal."""
    numero = (numero or "").strip()
    if not numero:
        raise ReglaDeNegocioError("Escribí el número de teléfono.")
    if cliente.telefonos.filter(numero=numero).exists():
        raise ReglaDeNegocioError("Ese teléfono ya está cargado.")
    principal = principal or not cliente.telefonos.exists()
    if principal:
        cliente.telefonos.update(principal=False)
    telefono = Telefono(cliente=cliente, numero=numero, principal=principal)
    telefono.full_clean()
    telefono.save()
    return telefono


@transaction.atomic
def marcar_telefono_principal(telefono):
    telefono.cliente.telefonos.exclude(pk=telefono.pk).update(principal=False)
    telefono.principal = True
    telefono.save(update_fields=["principal"])
    return telefono


@transaction.atomic
def quitar_telefono(telefono):
    """Si se quita el principal, el que queda más antiguo pasa a ser principal."""
    cliente, era_principal = telefono.cliente, telefono.principal
    telefono.delete()
    if era_principal:
        siguiente = cliente.telefonos.order_by("id").first()
        if siguiente:
            marcar_telefono_principal(siguiente)

def eliminar_cliente(cliente):
    try:
        cliente.delete()        # sus teléfonos se borran con él
    except ProtectedError:
        raise ReglaDeNegocioError("Tiene órdenes o ventas: no se puede eliminar sin perder ese historial.")
