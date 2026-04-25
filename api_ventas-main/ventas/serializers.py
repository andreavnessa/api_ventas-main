from decimal import Decimal

from django.contrib.auth.models import Group, User
from rest_framework import serializers

from .fiscal import calculate_invoice_amounts, calculate_line_amounts, get_current_fiscal_values, to_money
from .models import Cliente, DetalleVenta, Producto, Venta


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = '__all__'


class ProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = '__all__'


class DetalleVentaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetalleVenta
        fields = '__all__'


class VentaSerializer(serializers.ModelSerializer):
    detalles = DetalleVentaSerializer(many=True, read_only=True)

    class Meta:
        model = Venta
        fields = '__all__'


class DetalleVentaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetalleVenta
        fields = ['producto', 'cantidad']


class VentaCreateSerializer(serializers.ModelSerializer):
    detalles = DetalleVentaCreateSerializer(many=True)

    class Meta:
        model = Venta
        fields = ['cliente', 'detalles']

    def validate(self, data):
        detalles = data['detalles']

        for detalle in detalles:
            producto = detalle['producto']
            cantidad = detalle['cantidad']

            if producto.stock < cantidad:
                raise serializers.ValidationError(
                    f"Stock insuficiente para {producto.nombre}. Disponible: {producto.stock}"
                )

        return data

    def create(self, validated_data):
        detalles_data = validated_data.pop('detalles')
        fiscal_values = get_current_fiscal_values()
        tasa_dolar = to_money(fiscal_values['tasa_dolar'])
        iva_porcentaje = to_money(fiscal_values['iva_porcentaje'])

        subtotal_usd = Decimal('0')
        detalles_calculados = []

        for detalle in detalles_data:
            producto = detalle['producto']
            cantidad = detalle['cantidad']
            line_amounts = calculate_line_amounts(producto.precio, cantidad, tasa_dolar)
            subtotal_usd += line_amounts['subtotal_usd']
            detalles_calculados.append((detalle, line_amounts))

        fiscal_totals = calculate_invoice_amounts(subtotal_usd, tasa_dolar, iva_porcentaje)

        venta = Venta.objects.create(
            cliente=validated_data['cliente'],
            tasa_dolar_aplicada=tasa_dolar,
            iva_porcentaje_aplicado=iva_porcentaje,
            subtotal_usd=fiscal_totals['subtotal_usd'],
            subtotal_bs=fiscal_totals['subtotal_bs'],
            iva_usd=fiscal_totals['iva_usd'],
            iva_bs=fiscal_totals['iva_bs'],
            total=fiscal_totals['total_usd'],
            total_bs=fiscal_totals['total_bs'],
        )

        for detalle, line_amounts in detalles_calculados:
            producto = detalle['producto']
            cantidad = detalle['cantidad']

            DetalleVenta.objects.create(
                venta=venta,
                producto=producto,
                cantidad=cantidad,
                subtotal=line_amounts['subtotal_usd']
            )

            producto.stock -= cantidad
            producto.save(update_fields=['stock'])

        return venta


class UserSerializer(serializers.ModelSerializer):
    groups = serializers.SlugRelatedField(many=True, slug_field='name', queryset=Group.objects.all())

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'groups']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        groups = validated_data.pop('groups')
        user = User.objects.create_user(**validated_data)
        user.groups.set(groups)
        return user
