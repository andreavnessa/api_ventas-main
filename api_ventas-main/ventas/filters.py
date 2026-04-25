import django_filters
from .models import Cliente, Producto, Venta

class ClienteFilter(django_filters.FilterSet):
    nombre = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Cliente
        fields = ['nombre']


class ProductoFilter(django_filters.FilterSet):
    nombre = django_filters.CharFilter(lookup_expr='icontains')
    precio_min = django_filters.NumberFilter(field_name='precio', lookup_expr='gte')
    precio_max = django_filters.NumberFilter(field_name='precio', lookup_expr='lte')

    class Meta:
        model = Producto
        fields = ['nombre', 'precio_min', 'precio_max']


class VentaFilter(django_filters.FilterSet):
    fecha_inicio = django_filters.DateFilter(field_name='fecha', lookup_expr='gte')
    fecha_fin = django_filters.DateFilter(field_name='fecha', lookup_expr='lte')
    cliente = django_filters.CharFilter(field_name='cliente__nombre', lookup_expr='icontains')

    class Meta:
        model = Venta
        fields = ['fecha_inicio', 'fecha_fin', 'cliente']