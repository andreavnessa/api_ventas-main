from decimal import Decimal, ROUND_HALF_UP

from .models import ConfiguracionFiscal

MONEY_QUANTIZER = Decimal('0.01')
DEFAULT_TASA_DOLAR = Decimal('483.76')
DEFAULT_IVA_PORCENTAJE = Decimal('16.00')


def to_money(value):
    """
    Normaliza un valor monetario a dos decimales usando redondeo comercial.
    """
    if value is None:
        value = Decimal('0')
    return Decimal(str(value)).quantize(MONEY_QUANTIZER, rounding=ROUND_HALF_UP)


def get_current_fiscal_values():
    """
    Devuelve la configuración fiscal activa del sistema.
    """
    config = ConfiguracionFiscal.get_current()
    return config.as_currency_context()


def calculate_line_amounts(precio_unitario_usd, cantidad, tasa_dolar):
    """
    Calcula montos por línea en USD y Bs.
    """
    precio_unitario_usd = to_money(precio_unitario_usd)
    tasa_dolar = to_money(tasa_dolar)
    cantidad = Decimal(str(cantidad))

    precio_unitario_bs = to_money(precio_unitario_usd * tasa_dolar)
    subtotal_usd = to_money(precio_unitario_usd * cantidad)
    subtotal_bs = to_money(subtotal_usd * tasa_dolar)

    return {
        'precio_unitario_usd': precio_unitario_usd,
        'precio_unitario_bs': precio_unitario_bs,
        'subtotal_usd': subtotal_usd,
        'subtotal_bs': subtotal_bs,
    }


def calculate_invoice_amounts(subtotal_usd, tasa_dolar, iva_porcentaje):
    """
    Calcula subtotal, IVA y total en USD y Bs.
    """
    subtotal_usd = to_money(subtotal_usd)
    tasa_dolar = to_money(tasa_dolar)
    iva_porcentaje = to_money(iva_porcentaje)

    subtotal_bs = to_money(subtotal_usd * tasa_dolar)
    iva_usd = to_money(subtotal_usd * iva_porcentaje / Decimal('100'))
    iva_bs = to_money(subtotal_bs * iva_porcentaje / Decimal('100'))
    total_usd = to_money(subtotal_usd + iva_usd)
    total_bs = to_money(subtotal_bs + iva_bs)

    return {
        'subtotal_usd': subtotal_usd,
        'subtotal_bs': subtotal_bs,
        'iva_usd': iva_usd,
        'iva_bs': iva_bs,
        'total_usd': total_usd,
        'total_bs': total_bs,
        'tasa_dolar': tasa_dolar,
        'iva_porcentaje': iva_porcentaje,
    }
