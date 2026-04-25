from django.test import TestCase
from django.contrib.auth.models import User, Group
from rest_framework.test import APIClient
from rest_framework import status
from .models import Cliente, Producto, Venta, DetalleVenta


class VentasAPITestCase(TestCase):
    """Tests básicos para la API de Ventas"""
    
    def setUp(self):
        """Configuración inicial para los tests"""
        # Crear grupos
        self.admin_group, _ = Group.objects.get_or_create(name='admin')
        self.vendedor_group, _ = Group.objects.get_or_create(name='vendedor')
        self.lector_group, _ = Group.objects.get_or_create(name='lectura')
        
        # Crear usuarios
        self.admin_user = User.objects.create_user(
            username='admin', password='admin123', is_staff=True, is_superuser=True
        )
        self.vendedor_user = User.objects.create_user(
            username='vendedor', password='vendedor123'
        )
        self.vendedor_user.groups.add(self.vendedor_group)
        
        self.lector_user = User.objects.create_user(
            username='lector', password='lector123'
        )
        self.lector_user.groups.add(self.lector_group)
        
        # Crear datos de prueba
        self.cliente = Cliente.objects.create(
            nombre='Cliente Test',
            email='cliente@test.com',
            telefono='123456789'
        )
        
        self.producto = Producto.objects.create(
            nombre='Producto Test',
            precio=100.00,
            stock=50
        )
        
        # Cliente API
        self.client = APIClient()
    
    def test_health_check(self):
        """Test del endpoint health check"""
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')
    
    def test_login_jwt(self):
        """Test de autenticación JWT"""
        response = self.client.post('/api/token/', {
            'username': 'admin',
            'password': 'admin123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
    
    def test_admin_crud_cliente(self):
        """Test CRUD completo de clientes para Admin"""
        # Login como admin
        response = self.client.post('/api/token/', {
            'username': 'admin',
            'password': 'admin123'
        })
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Crear cliente
        data = {
            'nombre': 'Nuevo Cliente',
            'email': 'nuevo@test.com',
            'telefono': '987654321'
        }
        response = self.client.post('/api/admin/clientes/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Listar clientes
        response = self.client.get('/api/admin/clientes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
        # Actualizar cliente
        update_data = {'nombre': 'Cliente Actualizado'}
        response = self.client.patch('/api/admin/clientes/2/', update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nombre'], 'Cliente Actualizado')
        
        # Eliminar cliente
        response = self.client.delete('/api/admin/clientes/2/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_vendedor_solo_lectura(self):
        """Test de permisos de solo lectura para Vendedor"""
        # Login como vendedor
        response = self.client.post('/api/token/', {
            'username': 'vendedor',
            'password': 'vendedor123'
        })
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Puede leer
        response = self.client.get('/api/clientes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # No puede crear
        data = {'nombre': 'Cliente No Permitido', 'email': 'no@test.com'}
        response = self.client.post('/api/clientes/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_creacion_venta_con_stock_suficiente(self):
        """Test de creación de venta con stock suficiente"""
        # Login como vendedor
        response = self.client.post('/api/token/', {
            'username': 'vendedor',
            'password': 'vendedor123'
        })
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Crear venta
        data = {
            'cliente': self.cliente.id,
            'detalles': [
                {'producto': self.producto.id, 'cantidad': 5}
            ]
        }
        response = self.client.post('/api/ventas/crear/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verificar que se creó la venta
        self.assertEqual(Venta.objects.count(), 1)
        venta = Venta.objects.first()
        self.assertEqual(venta.total, 500.00)  # 5 * 100
        
        # Verificar que se actualizó el stock
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 45)  # 50 - 5
    
    def test_creacion_venta_con_stock_insuficiente(self):
        """Test de creación de venta con stock insuficiente"""
        # Login como vendedor
        response = self.client.post('/api/token/', {
            'username': 'vendedor',
            'password': 'vendedor123'
        })
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Intentar crear venta con más stock del disponible
        data = {
            'cliente': self.cliente.id,
            'detalles': [
                {'producto': self.producto.id, 'cantidad': 100}
            ]
        }
        response = self.client.post('/api/ventas/crear/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Stock insuficiente', str(response.data))
        
        # Verificar que no se creó la venta
        self.assertEqual(Venta.objects.count(), 0)
        
        # Verificar que el stock no cambió
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 50)
    
    def test_filtros_productos(self):
        """Test de filtros en endpoints de productos"""
        # Login como admin
        response = self.client.post('/api/token/', {
            'username': 'admin',
            'password': 'admin123'
        })
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Crear productos con diferentes precios
        Producto.objects.create(nombre='Producto Barato', precio=50.00, stock=10)
        Producto.objects.create(nombre='Producto Caro', precio=200.00, stock=5)
        
        # Filtrar por precio mínimo
        response = self.client.get('/api/admin/productos/?precio_min=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # Producto Test + Producto Caro
        
        # Filtrar por precio máximo
        response = self.client.get('/api/admin/productos/?precio_max=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # Producto Test + Producto Barato


class PermisosTestCase(TestCase):
    """Tests específicos para permisos y roles"""
    
    def setUp(self):
        """Configuración inicial para tests de permisos"""
        self.admin_group, _ = Group.objects.get_or_create(name='admin')
        self.vendedor_group, _ = Group.objects.get_or_create(name='vendedor')
        self.lector_group, _ = Group.objects.get_or_create(name='lectura')
        
        self.admin_user = User.objects.create_user(
            username='admin', password='admin123', is_staff=True
        )
        self.vendedor_user = User.objects.create_user(
            username='vendedor', password='vendedor123'
        )
        self.vendedor_user.groups.add(self.vendedor_group)
        
        self.lector_user = User.objects.create_user(
            username='lector', password='lector123'
        )
        self.lector_user.groups.add(self.lector_group)
        
        self.client = APIClient()
    
    def get_token_for_user(self, username, password):
        """Helper para obtener token JWT"""
        response = self.client.post('/api/token/', {
            'username': username,
            'password': password
        })
        return response.data['access']
    
    def test_admin_acceso_completo(self):
        """Test de acceso completo para Admin"""
        token = self.get_token_for_user('admin', 'admin123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Admin puede acceder a todos los endpoints
        endpoints = [
            '/api/admin/clientes/',
            '/api/admin/productos/',
            '/api/admin/ventas/',
            '/api/ventas/crear/'
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_200_OK,
                             f'Admin no puede acceder a {endpoint}')
    
    def test_vendedor_aceso_limitado(self):
        """Test de acceso limitado para Vendedor"""
        token = self.get_token_for_user('vendedor', 'vendedor123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Vendedor puede leer endpoints públicos
        public_endpoints = ['/api/clientes/', '/api/productos/', '/api/ventas/']
        for endpoint in public_endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_200_OK,
                             f'Vendedor no puede leer {endpoint}')
        
        # Vendedor no puede acceder a endpoints de admin
        admin_endpoints = ['/api/admin/clientes/', '/api/admin/productos/']
        for endpoint in admin_endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN,
                             f'Vendedor no debería acceder a {endpoint}')
        
        # Pero sí puede crear ventas
        response = self.client.post('/api/ventas/crear/', {})
        self.assertIn(response.status_code, 
                     [status.HTTP_400_BAD_REQUEST, status.HTTP_201_CREATED],
                     f'Vendedor debería poder crear ventas')
