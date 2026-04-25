from django import forms
from django.forms import formset_factory
from .models import Producto, Venta


class StyledFormMixin:
    def apply_bootstrap(self):
        for field in self.fields.values():
            widget = field.widget
            current_class = widget.attrs.get('class', '')
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = f'{current_class} form-check-input'.strip()
            else:
                widget.attrs['class'] = f'{current_class} form-control'.strip()


class ProductoForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'sku', 'categoria', 'descripcion', 'precio', 'stock', 'stock_minimo', 'activo']
        labels = {
            'precio': 'Precio de venta (PVP)',
            'stock': 'Stock inicial',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


class StockCargaForm(StyledFormMixin, forms.Form):
    producto = forms.ModelChoiceField(queryset=Producto.objects.order_by('nombre'), label='Producto')
    cantidad = forms.IntegerField(min_value=1, label='Cantidad a agregar')
    observacion = forms.CharField(required=False, label='Observación')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


class PrecioForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['precio']
        labels = {
            'precio': 'Nuevo PVP',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


class VentaForm(StyledFormMixin, forms.Form):
    cliente_nombre = forms.CharField(max_length=150, label='Nombre del cliente')
    cliente_cedula = forms.CharField(max_length=20, label='C.I. / Cédula del cliente')
    cliente_email = forms.EmailField(label='Email del cliente')
    cliente_telefono = forms.CharField(max_length=20, required=False, label='Teléfono del cliente')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_cliente_cedula(self):
        return self.cleaned_data['cliente_cedula'].strip().upper()

    def clean_cliente_email(self):
        return self.cleaned_data['cliente_email'].strip().lower()

    def clean_cliente_telefono(self):
        return self.cleaned_data['cliente_telefono'].strip()


class VentaItemForm(StyledFormMixin, forms.Form):
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).order_by('nombre'),
        label='Producto',
        required=False
    )
    cantidad = forms.IntegerField(min_value=1, label='Cantidad', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].label_from_instance = self._label_producto
        self.apply_bootstrap()

    def _label_producto(self, producto):
        return f'{producto.nombre} | SKU: {producto.sku} | Stock: {producto.stock} | Precio: ${producto.precio}'

    def clean(self):
        cleaned_data = super().clean()
        producto = cleaned_data.get('producto')
        cantidad = cleaned_data.get('cantidad')

        if producto and not cantidad:
            self.add_error('cantidad', 'Debes indicar la cantidad.')
        if cantidad and not producto:
            self.add_error('producto', 'Debes seleccionar un producto.')
        if producto and cantidad and producto.stock < cantidad:
            self.add_error('cantidad', f'Stock insuficiente para {producto.nombre}. Disponible: {producto.stock}')

        return cleaned_data


VentaItemFormSet = formset_factory(VentaItemForm, extra=8, can_delete=True)


class PagoVentaForm(StyledFormMixin, forms.Form):
    metodo_pago = forms.ChoiceField(choices=Venta.METODO_PAGO_CHOICES, label='Método de pago')
    referencia_pago = forms.CharField(
        max_length=100,
        required=False,
        label='Número de referencia',
        help_text='Obligatorio para transferencia y pago móvil.'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_referencia_pago(self):
        return self.cleaned_data['referencia_pago'].strip()

    def clean(self):
        cleaned_data = super().clean()
        metodo_pago = cleaned_data.get('metodo_pago')
        referencia_pago = cleaned_data.get('referencia_pago')

        if metodo_pago in {Venta.METODO_TRANSFERENCIA, Venta.METODO_PAGO_MOVIL} and not referencia_pago:
            self.add_error('referencia_pago', 'Debes indicar el número de referencia para este método de pago.')

        return cleaned_data
