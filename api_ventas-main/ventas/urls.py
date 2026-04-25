from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ClienteViewSet, ProductoViewSet, VentaViewSet, RegistrarVentaView,
    AdminClienteViewSet, AdminProductoViewSet, AdminVentaViewSet, UserView, AdminUserViewSet
)

# Router para endpoints públicos (solo lectura para Vendedor/Lector)
router = DefaultRouter()
router.register(r'clientes', ClienteViewSet, basename='cliente')
router.register(r'productos', ProductoViewSet, basename='producto')
router.register(r'ventas', VentaViewSet, basename='venta')

# Router para endpoints de Admin (CRUD completo)
admin_router = DefaultRouter()
admin_router.register(r'clientes', AdminClienteViewSet, basename='admin_cliente')
admin_router.register(r'productos', AdminProductoViewSet, basename='admin_producto')
admin_router.register(r'ventas', AdminVentaViewSet, basename='admin_venta')
admin_router.register(r'users', AdminUserViewSet, basename='admin_user')


urlpatterns = [
    # Endpoints públicos (lectura para todos los roles)
    path('', include(router.urls)),
    
    # Endpoint para crear ventas (Admin y Vendedor)
    path('crear/', RegistrarVentaView.as_view(), name='registrar_venta'),
    
    # Endpoints de Admin (CRUD completo)
    path('admin/', include(admin_router.urls)),
    
    # Endpoint para info de usuario
    path('user/', UserView.as_view(), name='user'),
]