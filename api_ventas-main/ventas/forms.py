from django import forms
from django.forms import formset_factory
from .models import Producto, Venta, Cliente
import re


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

    def clean_cliente_nombre(self):
        nombre = self.cleaned_data['cliente_nombre'].strip()
        if not nombre:
            raise forms.ValidationError('El nombre del cliente es obligatorio.')

        permitido = all((ch.isalpha() or ch.isspace()) for ch in nombre)
        if not permitido:
            raise forms.ValidationError('El nombre solo debe contener letras (sin números ni símbolos).')

        nombre = re.sub(r'\s+', ' ', nombre)
        return nombre

    def clean_cliente_cedula(self):
        cedula = self.cleaned_data['cliente_cedula'].strip()

        if not cedula:
            raise forms.ValidationError('La cédula del cliente es obligatoria.')

        if not cedula.isdigit():
            raise forms.ValidationError('La cédula solo debe contener números (sin letras ni símbolos).')

        if len(cedula) != 8:
            raise forms.ValidationError('La cédula debe tener exactamente 8 dígitos.')

        return cedula

    def clean_cliente_email(self):
        return self.cleaned_data['cliente_email'].strip().lower()

    def clean_cliente_telefono(self):
        telefono = self.cleaned_data['cliente_telefono'].strip()

        if not telefono:
            return ''

        if not telefono.isdigit():
            raise forms.ValidationError('El teléfono solo debe contener números (sin letras ni símbolos).')

        if len(telefono) != 11:
            raise forms.ValidationError('El teléfono debe tener exactamente 11 dígitos.')

        return telefono


class ClienteForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'cedula', 'email', 'telefono']
        labels = {
            'nombre': 'Nombre',
            'cedula': 'Cédula',
            'email': 'Email',
            'telefono': 'Teléfono',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_nombre(self):
        nombre = (self.cleaned_data.get('nombre') or '').strip()
        if not nombre:
            raise forms.ValidationError('El nombre es obligatorio.')

        permitido = all((ch.isalpha() or ch.isspace()) for ch in nombre)
        if not permitido:
            raise forms.ValidationError('El nombre solo debe contener letras (sin números ni símbolos).')

        return re.sub(r'\s+', ' ', nombre)

    def clean_cedula(self):
        cedula = (self.cleaned_data.get('cedula') or '').strip()
        if not cedula:
            raise forms.ValidationError('La cédula es obligatoria.')

        if not cedula.isdigit():
            raise forms.ValidationError('La cédula solo debe contener números (sin letras ni símbolos).')

        if len(cedula) != 8:
            raise forms.ValidationError('La cédula debe tener exactamente 8 dígitos.')

        return cedula

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        return email

    def clean_telefono(self):
        telefono = (self.cleaned_data.get('telefono') or '').strip()
        if not telefono:
            return ''

        if not telefono.isdigit():
            raise forms.ValidationError('El teléfono solo debe contener números (sin letras ni símbolos).')

        if len(telefono) != 11:
            raise forms.ValidationError('El teléfono debe tener exactamente 11 dígitos.')

        return telefono


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


VentaItemFormSet = formset_factory(VentaItemForm, extra=1, can_delete=True)


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
