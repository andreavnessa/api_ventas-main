#!/usr/bin/env python
"""
Script para configurar usuarios y datos de prueba para la API de Ventas

Uso:
    python create_users.py

Crea:
- Grupos de usuarios (vendedor, lector)
- Usuarios de prueba con contraseñas
- Datos de ejemplo (clientes, productos)
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api_ventas.settings')
django.setup()

from django.contrib.auth.models import User, Group, Permission
from ventas.models import Cliente, Producto

def create_groups_and_users():
    """
    Crea la estructura inicial de usuarios y datos de prueba
    para facilitar el desarrollo y testing de la API
    """
    print("🚀 Configurando usuarios y datos de prueba...")
    
    # Crear grupos
    vendedor_group, created = Group.objects.get_or_create(name='vendedor')
    lector_group, created = Group.objects.get_or_create(name='lectura')
    
    print(f"✅ Grupos creados: vendedor, lector")
    
    # Crear usuario vendedor
    vendedor_user, created = User.objects.get_or_create(
        username='vendedor',
        defaults={
            'email': 'vendedor@test.com',
            'first_name': 'Vendedor',
            'last_name': 'Test'
        }
    )
    if created:
        vendedor_user.set_password('vendedor123')
        vendedor_user.save()
        vendedor_user.groups.add(vendedor_group)
        print("✅ Usuario vendedor creado: vendedor / vendedor123")
    else:
        print("ℹ️  Usuario vendedor ya existe")
    
    # Crear usuario lector
    lector_user, created = User.objects.get_or_create(
        username='lector',
        defaults={
            'email': 'lector@test.com',
            'first_name': 'Lector',
            'last_name': 'Test'
        }
    )
    if created:
        lector_user.set_password('lector123')
        lector_user.save()
        lector_user.groups.add(lector_group)
        print("✅ Usuario lector creado: lector / lector123")
    else:
        print("ℹ️  Usuario lector ya existe")
    
    # Crear datos de prueba
    cliente, created = Cliente.objects.get_or_create(
        nombre="Cliente Test",
        defaults={
            'email': 'cliente@test.com',
            'telefono': '123456789'
        }
    )
    
    producto, created = Producto.objects.get_or_create(
        nombre="Producto Test",
        defaults={
            'precio': 100.00,
            'stock': 50
        }
    )
    
    print(f"✅ Cliente creado: {cliente.id} - {cliente.nombre}")
    print(f"✅ Producto creado: {producto.id} - {producto.nombre}")
    
    print("\n📋 Resumen de usuarios para pruebas:")
    print("🔹 Admin: Crea tu propio superusuario con 'python manage.py createsuperuser'")
    print("🔹 Vendedor: vendedor / vendedor123")
    print("🔹 Lector: lector / lector123")
    
    print("\n📝 IDs para pruebas de API:")
    print(f"🔹 Cliente ID: {cliente.id}")
    print(f"🔹 Producto ID: {producto.id}")
    
    print("\n🧪 Para probar la API:")
    print("1. Inicia el servidor: python manage.py runserver")
    print("2. Obtén token: POST http://localhost:8000/api/token/")
    print("3. Usa endpoints: http://localhost:8000/api/docs/")

if __name__ == '__main__':
    create_groups_and_users()
