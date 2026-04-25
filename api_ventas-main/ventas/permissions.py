from rest_framework.permissions import BasePermission
from rest_framework.permissions import IsAuthenticated


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)

class IsVendedor(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.groups.filter(name='vendedor').exists()
        
class IsLectura(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.groups.filter(name='lectura').exists()

class AdminVendedorLectura(BasePermission):
    """
    Admin O Vendedor O Lectura para métodos de solo lectura
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Métodos de solo lectura
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return (
                (request.user.is_staff or request.user.is_superuser) or
                request.user.groups.filter(name='vendedor').exists() or
                request.user.groups.filter(name='lectura').exists()
            )
        
        # Métodos de escritura → solo admin
        return request.user.is_staff or request.user.is_superuser

class IsAdminOrVendedor(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return (
            request.user.is_staff or
            request.user.is_superuser or
            request.user.groups.filter(name='vendedor').exists()
        )


class AdminVendedorLecturaMixin:
    """
    Admin → todo
    Vendedor → solo ver
    Lectura → solo ver
    """
    def get_permissions(self):
        return [IsAuthenticated(), AdminVendedorLectura()]
