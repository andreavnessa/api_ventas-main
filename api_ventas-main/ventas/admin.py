from decimal import Decimal

from django import forms
from django.contrib import admin

from .models import ConfiguracionFiscal, Producto


@admin.register(ConfiguracionFiscal)
class ConfiguracionFiscalAdmin(admin.ModelAdmin):
    list_display = ("id", "tasa_dolar", "iva_porcentaje", "activa", "actualizado_en")
    list_filter = ("activa",)
    search_fields = ("tasa_dolar", "iva_porcentaje")
    ordering = ("-activa", "-actualizado_en")


class ProductoAdminForm(forms.ModelForm):
    precio_bs = forms.DecimalField(
        required=False,
        max_digits=14,
        decimal_places=2,
        label="Precio en Bs (opcional)",
        help_text="Si se llena, se convertirá a USD con la tasa del dólar activa.",
    )

    class Meta:
        model = Producto
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # precarga: si quieres, podrías calcular desde self.instance.precio,
        # pero para evitar confusiones dejamos vacío por defecto.
        self.fields["precio_bs"].initial = None

    def clean(self):
        cleaned_data = super().clean()
        precio_bs = cleaned_data.get("precio_bs")

        if precio_bs is not None:
            config = ConfiguracionFiscal.get_current()
            tasa = config.tasa_dolar
            if tasa is None or Decimal(tasa) == 0:
                raise forms.ValidationError("La tasa del dólar activa no puede ser 0.")

            # Tu modelo guarda Producto.precio como Decimal (usado luego como USD en cálculos).
            cleaned_data["precio"] = (Decimal(precio_bs) / Decimal(tasa)).quantize(
                Decimal("0.01")
            )

        return cleaned_data


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    form = ProductoAdminForm
    list_display = ("id", "nombre", "sku", "categoria", "precio", "stock", "stock_minimo", "activo")
    list_filter = ("activo", "categoria")
    search_fields = ("nombre", "sku")
