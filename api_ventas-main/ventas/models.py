from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models, transaction


class ConfiguracionFiscal(models.Model):
    tasa_dolar = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('483.76'))
    iva_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('16.00'))
    activa = models.BooleanField(default=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración fiscal'
        verbose_name_plural = 'Configuraciones fiscales'
        ordering = ['-activa', '-actualizado_en', '-id']

    def __str__(self):
        estado = 'Activa' if self.activa else 'Inactiva'
        return f'USD {self.tasa_dolar} / IVA {self.iva_porcentaje}% ({estado})'

    def save(self, *args, **kwargs):
        if self.activa:
            with transaction.atomic():
                ConfiguracionFiscal.objects.filter(activa=True).exclude(pk=self.pk).update(activa=False)
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    @classmethod
    def get_current(cls):
        config = cls.objects.filter(activa=True).order_by('-actualizado_en', '-id').first()
        if config is not None:
            return config
        return cls.objects.create(activa=True)

    def as_currency_context(self):
        return {
            'tasa_dolar': self.tasa_dolar,
            'iva_porcentaje': self.iva_porcentaje,
        }


class Cliente(models.Model):
    nombre = models.CharField(max_length=150)
    cedula = models.CharField(max_length=20, blank=True, default='')
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    nombre = models.CharField(max_length=150)
    sku = models.CharField(max_length=50, unique=True)
    categoria = models.CharField(max_length=100, default='General')
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} ({self.sku})"


class Venta(models.Model):
    METODO_EFECTIVO = 'efectivo'
    METODO_TRANSFERENCIA = 'transferencia'
    METODO_PAGO_MOVIL = 'pago_movil'
    METODO_PAGO_CHOICES = [
        (METODO_EFECTIVO, 'Efectivo'),
        (METODO_TRANSFERENCIA, 'Transferencia'),
        (METODO_PAGO_MOVIL, 'Pago móvil'),
    ]

    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_PAGADO = 'pagado'
    ESTADO_CANCELADO = 'cancelado'
    ESTADO_PAGO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_PAGADO, 'Pagado'),
        (ESTADO_CANCELADO, 'Cancelado'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    tasa_dolar_aplicada = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('483.76'))
    iva_porcentaje_aplicado = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('16.00'))
    subtotal_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal_bs = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    iva_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    iva_bs = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_bs = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES, default=METODO_EFECTIVO)
    referencia_pago = models.CharField(max_length=100, blank=True)
    estado_pago = models.CharField(max_length=20, choices=ESTADO_PAGO_CHOICES, default=ESTADO_PENDIENTE)

    def __str__(self):
        return f"Venta {self.id} - {self.cliente}"


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, related_name='detalles', on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.producto} x {self.cantidad}"


class MovimientoInventario(models.Model):
    TIPO_ENTRADA = 'entrada'
    TIPO_AJUSTE = 'ajuste'
    TIPO_SALIDA_VENTA = 'salida_venta'
    TIPO_CHOICES = [
        (TIPO_ENTRADA, 'Entrada'),
        (TIPO_AJUSTE, 'Ajuste'),
        (TIPO_SALIDA_VENTA, 'Salida por venta'),
    ]

    producto = models.ForeignKey(Producto, related_name='movimientos', on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_ENTRADA)
    cantidad = models.PositiveIntegerField()
    observacion = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.producto} - {self.tipo} ({self.cantidad})"
