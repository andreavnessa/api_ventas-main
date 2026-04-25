from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from .models import Cliente, Producto, Venta

def crear_roles():
    admin_group, _ = Group.objects.get_or_create(name='admin')
    vendedor_group, _ = Group.objects.get_or_create(name='vendedor')
    lectura_group, _ = Group.objects.get_or_create(name='lectura')

    # Permisos de modelos
    cliente_ct = ContentType.objects.get_for_model(Cliente)
    producto_ct = ContentType.objects.get_for_model(Producto)
    venta_ct = ContentType.objects.get_for_model(Venta)

    # Admin: todos los permisos
    admin_group.permissions.set(Permission.objects.all())

    # Vendedor: puede ver y crear ventas, ver clientes y productos
    vendedor_group.permissions.set([
        Permission.objects.get(codename='view_cliente'),
        Permission.objects.get(codename='view_producto'),
        Permission.objects.get(codename='view_venta'),
        Permission.objects.get(codename='add_venta'),
    ])

    # Lectura: solo ver
    lectura_group.permissions.set([
        Permission.objects.get(codename='view_cliente'),
        Permission.objects.get(codename='view_producto'),
        Permission.objects.get(codename='view_venta'),
    ])