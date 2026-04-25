from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from textwrap import wrap
from typing import Any
import struct
import zlib


PAGE_WIDTH = 595.28
PAGE_HEIGHT = 841.89
MARGIN = 36
TOP_BAND_HEIGHT = 66
INFO_BAND_HEIGHT = 44
TITLE_FONT_SIZE = 20
BODY_FONT_SIZE = 9.5
BODY_LEADING = 12
MAX_BODY_LINES_PER_PAGE = 40

COMPANY_NAME = "Dr. Antojos"
COMPANY_RIF = "J506024500"
DOCUMENT_TITLE = "REPORTE QUINCENAL"

HEADER_BG = (0.11, 0.27, 0.45)
HEADER_ACCENT = (0.86, 0.29, 0.15)
LIGHT_BG = (0.96, 0.97, 0.98)
CARD_BG = (0.99, 0.99, 1.0)
TEXT_DARK = (0.15, 0.18, 0.22)
TEXT_MUTED = (0.45, 0.49, 0.54)
WHITE = (1.0, 1.0, 1.0)

SUMMARY_CARD_GAP = 12
SUMMARY_CARD_HEIGHT = 58
SUMMARY_CARD_BOTTOM_GAP = 14

IMAGE_XOBJECT_NAME = "Im1"
LOGO_PATH = Path(__file__).resolve().parent / "static" / "ventas" / "img" / "logo.png"

SECTION_TITLES = {
    "Resumen general",
    "Resumen financiero",
    "Métodos de pago",
    "Productos más vendidos",
    "Detalle de ventas",
}


def _escape_pdf_text(text: Any) -> str:
    value = "" if text is None else str(text)
    return (
        value.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r\n", " ")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def _format_money(value: Any) -> str:
    try:
        return f"{Decimal(str(value or 0)):.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return "0.00"


def _format_integer(value: Any) -> str:
    try:
        return str(int(value or 0))
    except (TypeError, ValueError):
        return "0"


def _format_date(value: Any) -> str:
    if not value:
        return "N/A"
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _format_datetime(value: Any) -> str:
    if not value:
        return "N/A"
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y %H:%M")
    return str(value)


def _estimate_text_width(text: str, font_size: float, bold: bool = False) -> float:
    factor = 0.56 if bold else 0.52
    return len(text) * font_size * factor


def _append_wrapped(lines: list[str], text: str, width: int = 92, subsequent_indent: str = "  ") -> None:
    wrapped = wrap(
        text,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
        replace_whitespace=False,
    )
    if not wrapped:
        lines.append("")
        return

    lines.append(wrapped[0])
    for segment in wrapped[1:]:
        lines.append(f"{subsequent_indent}{segment}")


@lru_cache(maxsize=1)
def _load_logo_image_object() -> tuple[bytes, int, int] | None:
    if not LOGO_PATH.exists():
        return None

    try:
        data = LOGO_PATH.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            return None

        offset = 8
        width = height = bit_depth = color_type = compression = filter_method = interlace = None
        idat_parts: list[bytes] = []

        while offset + 8 <= len(data):
            if offset + 8 > len(data):
                return None

            length = struct.unpack(">I", data[offset:offset + 4])[0]
            offset += 4
            chunk_type = data[offset:offset + 4]
            offset += 4

            if offset + length > len(data):
                return None

            chunk_data = data[offset:offset + length]
            offset += length

            if offset + 4 > len(data):
                return None

            offset += 4  # CRC

            if chunk_type == b"IHDR":
                width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", chunk_data)
            elif chunk_type == b"IDAT":
                idat_parts.append(chunk_data)
            elif chunk_type == b"IEND":
                break

        if not idat_parts or width is None or height is None:
            return None

        if bit_depth != 8 or compression != 0 or filter_method != 0 or interlace != 0:
            return None

        bytes_per_input_pixel = {
            0: 1,  # grayscale
            2: 3,  # RGB
            4: 2,  # grayscale + alpha
            6: 4,  # RGBA
        }.get(color_type)

        if bytes_per_input_pixel is None:
            return None

        compressed = zlib.decompress(b"".join(idat_parts))
        row_bytes = width * bytes_per_input_pixel
        expected_len = height * (row_bytes + 1)
        if len(compressed) < expected_len:
            return None

        def paeth_predictor(a: int, b: int, c: int) -> int:
            p = a + b - c
            pa = abs(p - a)
            pb = abs(p - b)
            pc = abs(p - c)
            if pa <= pb and pa <= pc:
                return a
            if pb <= pc:
                return b
            return c

        rgb_bytes = bytearray()
        previous_row = bytearray(row_bytes)
        source_offset = 0

        for _ in range(height):
            filter_type = compressed[source_offset]
            source_offset += 1

            scanline = bytearray(compressed[source_offset:source_offset + row_bytes])
            source_offset += row_bytes

            reconstructed = bytearray(row_bytes)

            if filter_type == 0:
                reconstructed[:] = scanline
            elif filter_type == 1:
                for index in range(row_bytes):
                    left = reconstructed[index - bytes_per_input_pixel] if index >= bytes_per_input_pixel else 0
                    reconstructed[index] = (scanline[index] + left) & 0xFF
            elif filter_type == 2:
                for index in range(row_bytes):
                    up = previous_row[index] if previous_row else 0
                    reconstructed[index] = (scanline[index] + up) & 0xFF
            elif filter_type == 3:
                for index in range(row_bytes):
                    left = reconstructed[index - bytes_per_input_pixel] if index >= bytes_per_input_pixel else 0
                    up = previous_row[index] if previous_row else 0
                    reconstructed[index] = (scanline[index] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                for index in range(row_bytes):
                    left = reconstructed[index - bytes_per_input_pixel] if index >= bytes_per_input_pixel else 0
                    up = previous_row[index] if previous_row else 0
                    up_left = previous_row[index - bytes_per_input_pixel] if index >= bytes_per_input_pixel else 0
                    reconstructed[index] = (scanline[index] + paeth_predictor(left, up, up_left)) & 0xFF
            else:
                return None

            previous_row = reconstructed

            if color_type == 2:
                rgb_bytes.extend(reconstructed)
            elif color_type == 0:
                for gray in reconstructed:
                    rgb_bytes.extend((gray, gray, gray))
            elif color_type == 4:
                for index in range(0, row_bytes, 2):
                    gray = reconstructed[index]
                    alpha = reconstructed[index + 1]
                    value = (gray * alpha + 255 * (255 - alpha) + 127) // 255
                    rgb_bytes.extend((value, value, value))
            elif color_type == 6:
                for index in range(0, row_bytes, 4):
                    red = reconstructed[index]
                    green = reconstructed[index + 1]
                    blue = reconstructed[index + 2]
                    alpha = reconstructed[index + 3]
                    rgb_bytes.extend(
                        (
                            (red * alpha + 255 * (255 - alpha) + 127) // 255,
                            (green * alpha + 255 * (255 - alpha) + 127) // 255,
                            (blue * alpha + 255 * (255 - alpha) + 127) // 255,
                        )
                    )

        final_stream = zlib.compress(bytes(rgb_bytes))
        payload = (
            b"<< /Type /XObject /Subtype /Image /Width "
            + str(width).encode("ascii")
            + b" /Height "
            + str(height).encode("ascii")
            + b" /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length "
            + str(len(final_stream)).encode("ascii")
            + b" >>\nstream\n"
            + final_stream
            + b"\nendstream"
        )
        return payload, width, height
    except Exception:
        return None


def _build_report_lines(report: dict[str, Any]) -> list[str]:
    periodo = report.get("periodo", {})
    resumen = report.get("resumen", {})
    medios_pago = report.get("medios_pago", [])
    productos_top = report.get("productos_top", [])
    ventas_detalladas = report.get("ventas_detalladas", [])

    periodo_label = periodo.get("label", "Reporte quincenal")
    fecha_inicio = _format_date(periodo.get("fecha_inicio"))
    fecha_fin = _format_date(periodo.get("fecha_fin"))
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")

    lines: list[str] = []

    lines.append("Resumen general")
    _append_wrapped(lines, f"Período: {periodo_label}")
    _append_wrapped(lines, f"Fechas: {fecha_inicio} - {fecha_fin}")
    _append_wrapped(lines, f"Generado: {generated_at}")
    lines.append("")
    _append_wrapped(lines, f"Ventas registradas: {_format_integer(resumen.get('ventas_registradas'))}")
    _append_wrapped(lines, f"Ventas pagadas: {_format_integer(resumen.get('ventas_pagadas'))}")
    _append_wrapped(lines, f"Ventas pendientes: {_format_integer(resumen.get('ventas_pendientes'))}")
    _append_wrapped(lines, f"Ventas canceladas: {_format_integer(resumen.get('ventas_canceladas'))}")
    _append_wrapped(lines, f"Unidades vendidas: {_format_integer(resumen.get('total_unidades_vendidas'))}")

    lines.append("")
    lines.append("Resumen financiero")
    _append_wrapped(lines, f"Subtotal USD: ${_format_money(resumen.get('subtotal_usd'))}")
    _append_wrapped(lines, f"Subtotal Bs: Bs {_format_money(resumen.get('subtotal_bs'))}")
    _append_wrapped(lines, f"IVA USD: ${_format_money(resumen.get('iva_usd'))}")
    _append_wrapped(lines, f"IVA Bs: Bs {_format_money(resumen.get('iva_bs'))}")
    _append_wrapped(lines, f"Total cobrado USD: ${_format_money(resumen.get('total_cobrado_usd'))}")
    _append_wrapped(lines, f"Total cobrado Bs: Bs {_format_money(resumen.get('total_cobrado_bs'))}")
    _append_wrapped(lines, f"Total facturado USD: ${_format_money(resumen.get('total_facturado_usd'))}")
    _append_wrapped(lines, f"Total facturado Bs: Bs {_format_money(resumen.get('total_facturado_bs'))}")
    _append_wrapped(lines, f"Ticket promedio USD: ${_format_money(resumen.get('ticket_promedio_usd'))}")
    _append_wrapped(lines, f"Ticket promedio Bs: Bs {_format_money(resumen.get('ticket_promedio_bs'))}")

    lines.append("")
    lines.append("Métodos de pago")
    if medios_pago:
        for item in medios_pago:
            _append_wrapped(
                lines,
                (
                    f"- {item.get('metodo_pago') or 'N/A'}: "
                    f"{_format_integer(item.get('cantidad'))} ventas | "
                    f"USD {_format_money(item.get('total_usd'))} | "
                    f"Bs {_format_money(item.get('total_bs'))}"
                ),
            )
    else:
        lines.append("No hay ventas pagadas en este período.")

    lines.append("")
    lines.append("Productos más vendidos")
    if productos_top:
        for producto in productos_top:
            sku = producto.get("producto__sku") or "Sin SKU"
            nombre = producto.get("producto__nombre") or "Sin nombre"
            _append_wrapped(
                lines,
                (
                    f"- {nombre} ({sku}) | "
                    f"Unidades: {_format_integer(producto.get('unidades'))} | "
                    f"Subtotal USD: ${_format_money(producto.get('subtotal_usd'))}"
                ),
            )
    else:
        lines.append("No hay productos vendidos en este período.")

    lines.append("")
    lines.append("Detalle de ventas")
    if ventas_detalladas:
        for item in ventas_detalladas:
            venta = item.get("venta")
            detalles = item.get("detalles", [])
            _append_wrapped(
                lines,
                (
                    f"Venta #{getattr(venta, 'id', 'N/A')} | "
                    f"Cliente: {getattr(getattr(venta, 'cliente', None), 'nombre', 'N/A')} | "
                    f"Fecha: {_format_datetime(getattr(venta, 'fecha', None))} | "
                    f"Estado: {getattr(venta, 'get_estado_pago_display', lambda: 'N/A')()} | "
                    f"Método: {getattr(venta, 'get_metodo_pago_display', lambda: 'N/A')()}"
                ),
            )
            _append_wrapped(
                lines,
                (
                    f"  Subtotal USD: ${_format_money(getattr(venta, 'subtotal_usd', None) or getattr(venta, 'total', None))} | "
                    f"IVA USD: ${_format_money(getattr(venta, 'iva_usd', None))} | "
                    f"Total USD: ${_format_money(getattr(venta, 'total', None))} | "
                    f"Total Bs: Bs {_format_money(getattr(venta, 'total_bs', None))}"
                ),
            )
            _append_wrapped(lines, f"  Unidades en la venta: {_format_integer(item.get('unidades'))}")
            if detalles:
                for detalle in detalles:
                    producto = getattr(detalle, "producto", None)
                    producto_nombre = getattr(producto, "nombre", "Producto")
                    cantidad = _format_integer(getattr(detalle, "cantidad", None))
                    subtotal = _format_money(getattr(detalle, "subtotal", None))
                    _append_wrapped(
                        lines,
                        f"    • {producto_nombre} | Cantidad: {cantidad} | Subtotal USD: ${subtotal}",
                    )
            else:
                lines.append("    Sin detalles de productos.")
            lines.append("")
    else:
        lines.append("No existen ventas registradas para esta quincena.")

    return lines


def _chunk_lines(lines: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        return [lines]
    return [lines[index:index + size] for index in range(0, len(lines), size)] or [[]]


def _draw_rect(
    commands: list[str],
    x: float,
    y: float,
    width: float,
    height: float,
    fill: tuple[float, float, float] | None = None,
    stroke: tuple[float, float, float] | None = None,
    line_width: float = 1.0,
) -> None:
    commands.append("q")
    if fill is not None:
        commands.append(f"{fill[0]:.3f} {fill[1]:.3f} {fill[2]:.3f} rg")
    if stroke is not None:
        commands.append(f"{stroke[0]:.3f} {stroke[1]:.3f} {stroke[2]:.3f} RG")
        commands.append(f"{line_width:.2f} w")
    commands.append(f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re")
    if fill is not None and stroke is not None:
        commands.append("B")
    elif fill is not None:
        commands.append("f")
    else:
        commands.append("S")
    commands.append("Q")


def _draw_line(
    commands: list[str],
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: tuple[float, float, float] = TEXT_MUTED,
    line_width: float = 0.75,
) -> None:
    commands.append("q")
    commands.append(f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} RG")
    commands.append(f"{line_width:.2f} w")
    commands.append(f"{x1:.2f} {y1:.2f} m")
    commands.append(f"{x2:.2f} {y2:.2f} l")
    commands.append("S")
    commands.append("Q")


def _draw_text(
    commands: list[str],
    x: float,
    y: float,
    text: str,
    font: str = "F1",
    size: float = BODY_FONT_SIZE,
    color: tuple[float, float, float] = TEXT_DARK,
    align: str = "left",
    width: float | None = None,
) -> None:
    if text is None:
        return

    value = str(text)
    if not value:
        return

    draw_x = x
    if align != "left" and width is not None:
        estimated = _estimate_text_width(value, size, bold=font == "F2")
        if align == "center":
            draw_x = x + max(0.0, (width - estimated) / 2.0)
        elif align == "right":
            draw_x = x + max(0.0, width - estimated)

    commands.extend([
        "BT",
        f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} rg",
        f"/{font} {size:.2f} Tf",
        f"{draw_x:.2f} {y:.2f} Td",
        f"({_escape_pdf_text(value)}) Tj",
        "ET",
    ])


def _draw_image(commands: list[str], x: float, y: float, width: float, height: float, resource_name: str = IMAGE_XOBJECT_NAME) -> None:
    commands.extend([
        "q",
        f"{width:.2f} 0 0 {height:.2f} {x:.2f} {y:.2f} cm",
        f"/{resource_name} Do",
        "Q",
    ])


def _draw_metric_card(
    commands: list[str],
    x: float,
    y: float,
    width: float,
    height: float,
    label: str,
    value: str,
    subtitle: str | None = None,
    accent: tuple[float, float, float] = HEADER_BG,
    value_size: float = 12.0,
) -> None:
    _draw_rect(commands, x, y, width, height, fill=CARD_BG, stroke=(0.82, 0.85, 0.89), line_width=0.8)
    _draw_rect(commands, x, y + height - 4, width, 4, fill=accent)
    _draw_text(commands, x + 10, y + height - 14, label, font="F2", size=7.6, color=TEXT_MUTED)
    _draw_text(commands, x + 10, y + height - 31, value, font="F2", size=value_size, color=accent)
    if subtitle:
        _draw_text(commands, x + 10, y + 11, subtitle, font="F1", size=7.2, color=TEXT_MUTED)


def _draw_summary_cards(commands: list[str], report: dict[str, Any], top_y: float) -> float:
    periodo = report.get("periodo", {})
    resumen = report.get("resumen", {})
    fecha_inicio = _format_date(periodo.get("fecha_inicio"))
    fecha_fin = _format_date(periodo.get("fecha_fin"))

    card_width = (PAGE_WIDTH - (MARGIN * 2) - (SUMMARY_CARD_GAP * 3)) / 4.0
    card_y = top_y - SUMMARY_CARD_HEIGHT

    cards = [
        (
            "Período",
            f"Quincena {periodo.get('quincena', 'N/A')}",
            f"{fecha_inicio} al {fecha_fin}",
            HEADER_BG,
            11.2,
        ),
        (
            "Ventas registradas",
            _format_integer(resumen.get("ventas_registradas")),
            f"Pagadas: {_format_integer(resumen.get('ventas_pagadas'))} · Pendientes: {_format_integer(resumen.get('ventas_pendientes'))}",
            HEADER_ACCENT,
            12.0,
        ),
        (
            "Total cobrado",
            f"$ {_format_money(resumen.get('total_cobrado_usd'))}",
            f"Bs {_format_money(resumen.get('total_cobrado_bs'))}",
            (0.15, 0.55, 0.32),
            12.0,
        ),
        (
            "Total facturado",
            f"$ {_format_money(resumen.get('total_facturado_usd'))}",
            f"Unidades: {_format_integer(resumen.get('total_unidades_vendidas'))}",
            (0.48, 0.32, 0.75),
            12.0,
        ),
    ]

    for index, (label, value, subtitle, accent, value_size) in enumerate(cards):
        x = MARGIN + (index * (card_width + SUMMARY_CARD_GAP))
        _draw_metric_card(
            commands,
            x,
            card_y,
            card_width,
            SUMMARY_CARD_HEIGHT,
            label,
            value,
            subtitle=subtitle,
            accent=accent,
            value_size=value_size,
        )

    return card_y - SUMMARY_CARD_BOTTOM_GAP


def _draw_header(
    commands: list[str],
    period_label: str,
    fecha_inicio: str,
    fecha_fin: str,
    generated_at: str,
    page_number: int,
    total_pages: int,
    logo_info: tuple[int, int] | None = None,
) -> None:
    band_y = PAGE_HEIGHT - TOP_BAND_HEIGHT
    card_y = band_y - INFO_BAND_HEIGHT

    _draw_rect(commands, 0, band_y, PAGE_WIDTH, TOP_BAND_HEIGHT, fill=HEADER_BG)
    _draw_rect(commands, MARGIN, card_y, PAGE_WIDTH - (MARGIN * 2), INFO_BAND_HEIGHT, fill=CARD_BG, stroke=(0.80, 0.84, 0.88), line_width=0.8)

    _draw_text(commands, MARGIN, PAGE_HEIGHT - 30, COMPANY_NAME, font="F2", size=TITLE_FONT_SIZE, color=WHITE)
    _draw_text(commands, MARGIN, PAGE_HEIGHT - 46, f"RIF: {COMPANY_RIF}", font="F1", size=10, color=WHITE)
    _draw_text(commands, MARGIN, PAGE_HEIGHT - 58, DOCUMENT_TITLE, font="F2", size=11, color=WHITE)

    logo_box_w = 60
    logo_box_h = 48
    logo_box_x = PAGE_WIDTH - MARGIN - logo_box_w
    logo_box_y = PAGE_HEIGHT - 56

    if logo_info:
        logo_width, logo_height = logo_info
        _draw_rect(commands, logo_box_x, logo_box_y, logo_box_w, logo_box_h, fill=WHITE, stroke=(0.88, 0.90, 0.93), line_width=0.7)
        inner_padding = 4.0
        scale = min((logo_box_w - inner_padding * 2) / logo_width, (logo_box_h - inner_padding * 2) / logo_height)
        render_w = logo_width * scale
        render_h = logo_height * scale
        render_x = logo_box_x + (logo_box_w - render_w) / 2.0
        render_y = logo_box_y + (logo_box_h - render_h) / 2.0
        _draw_image(commands, render_x, render_y, render_w, render_h)
    else:
        _draw_rect(commands, logo_box_x, logo_box_y, logo_box_w, logo_box_h, fill=(0.15, 0.34, 0.54), stroke=WHITE, line_width=1.0)
        _draw_text(commands, logo_box_x, logo_box_y + 24, "LOGO", font="F2", size=14, color=WHITE, align="center", width=logo_box_w)
        _draw_text(commands, logo_box_x, logo_box_y + 10, "Espacio para logo", font="F1", size=7.5, color=WHITE, align="center", width=logo_box_w)

    left_col_x = MARGIN + 10
    mid_col_x = MARGIN + 180
    right_col_x = MARGIN + 365
    label_y = card_y + 28
    value_y = card_y + 14

    _draw_text(commands, left_col_x, label_y, "Documento", font="F2", size=8.5, color=TEXT_MUTED)
    _draw_text(commands, left_col_x, value_y, "Reporte quincenal", font="F2", size=11, color=TEXT_DARK)

    _draw_text(commands, mid_col_x, label_y, "Período", font="F2", size=8.5, color=TEXT_MUTED)
    _draw_text(commands, mid_col_x, value_y, period_label, font="F1", size=10.2, color=TEXT_DARK)

    _draw_text(commands, right_col_x, label_y, "Emitido", font="F2", size=8.5, color=TEXT_MUTED)
    _draw_text(commands, right_col_x, value_y, generated_at, font="F1", size=10.2, color=TEXT_DARK)

    info_line_y = card_y - 6
    _draw_line(commands, MARGIN, info_line_y, PAGE_WIDTH - MARGIN, info_line_y, color=(0.86, 0.88, 0.92), line_width=0.6)

    _draw_text(commands, MARGIN, card_y - 18, f"Período: {fecha_inicio} al {fecha_fin}", font="F1", size=8.8, color=TEXT_MUTED)
    _draw_text(
        commands,
        PAGE_WIDTH - MARGIN - 150,
        card_y - 18,
        f"Página {page_number} de {total_pages}",
        font="F1",
        size=8.8,
        color=TEXT_MUTED,
        align="right",
        width=150,
    )


def _draw_footer(commands: list[str], page_number: int, total_pages: int) -> None:
    footer_y = 46
    _draw_line(commands, MARGIN, footer_y + 12, PAGE_WIDTH - MARGIN, footer_y + 12, color=(0.84, 0.86, 0.90), line_width=0.6)
    _draw_text(commands, MARGIN, footer_y, f"{COMPANY_NAME} • RIF {COMPANY_RIF}", font="F1", size=8.2, color=TEXT_MUTED)
    _draw_text(
        commands,
        PAGE_WIDTH - MARGIN - 120,
        footer_y,
        f"Página {page_number} de {total_pages}",
        font="F1",
        size=8.2,
        color=TEXT_MUTED,
        align="right",
        width=120,
    )


def _draw_body_lines(commands: list[str], lines: list[str], start_x: float, start_y: float, width: float) -> None:
    y = start_y

    for line in lines:
        if y < 70:
            break

        text = line.strip()
        if not text:
            y -= 4
            continue

        if text in SECTION_TITLES:
            _draw_rect(commands, start_x, y - 10, width, 16, fill=LIGHT_BG, stroke=(0.80, 0.84, 0.88), line_width=0.6)
            _draw_text(commands, start_x + 8, y, text, font="F2", size=11.2, color=HEADER_BG)
            _draw_line(commands, start_x, y - 13, start_x + width, y - 13, color=HEADER_ACCENT, line_width=0.75)
            y -= 19
            continue

        indent = 0.0
        size = BODY_FONT_SIZE
        if line.startswith("    •") or line.startswith("    -"):
            indent = 18
            size = 9.0
        elif line.startswith("    "):
            indent = 16
            size = 9.0
        elif line.startswith("  "):
            indent = 8
            size = 9.3
        elif text.startswith("• ") or text.startswith("- "):
            indent = 12
            size = 9.3

        if text.startswith("Venta #"):
            _draw_text(commands, start_x, y, text, font="F2", size=9.4, color=TEXT_DARK)
        elif text.startswith("Subtotal USD:") or text.startswith("IVA USD:") or text.startswith("Total USD:") or text.startswith("Total Bs:"):
            _draw_text(commands, start_x + indent, y, text, font="F1", size=size, color=TEXT_DARK)
        elif text.startswith("Unidades en la venta:"):
            _draw_text(commands, start_x + indent, y, text, font="F1", size=size, color=TEXT_MUTED)
        elif text.startswith("No hay") or text.startswith("No existen") or text.startswith("Sin detalles"):
            _draw_text(commands, start_x + indent, y, text, font="F1", size=size, color=TEXT_MUTED)
        else:
            _draw_text(commands, start_x + indent, y, text, font="F1", size=size, color=TEXT_DARK)

        y -= BODY_LEADING if size >= 9.4 else 11


def _build_content_stream(commands: list[str]) -> bytes:
    return "\n".join(commands).encode("latin-1", "replace")


def _build_pdf_bytes(objects: dict[int, bytes]) -> bytes:
    max_object_number = max(objects)

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    offsets = [0] * (max_object_number + 1)

    for number in range(1, max_object_number + 1):
        payload = objects[number]
        offsets[number] = len(pdf)
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(payload)
        pdf.extend(b"\nendobj\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {max_object_number + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for number in range(1, max_object_number + 1):
        pdf.extend(f"{offsets[number]:010d} 00000 n \n".encode("ascii"))

    pdf.extend(
        f"trailer\n<< /Size {max_object_number + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF".encode(
            "ascii"
        )
    )
    return bytes(pdf)


def build_quincenal_report_pdf(report: dict[str, Any]) -> bytes:
    periodo = report.get("periodo", {})
    periodo_label = periodo.get("label", "Reporte quincenal")
    fecha_inicio = _format_date(periodo.get("fecha_inicio"))
    fecha_fin = _format_date(periodo.get("fecha_fin"))
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")

    body_lines = _build_report_lines(report)
    lines_per_page = max(1, MAX_BODY_LINES_PER_PAGE)
    page_bodies = _chunk_lines(body_lines, lines_per_page)

    logo_asset = _load_logo_image_object()
    logo_info: tuple[int, int] | None = None

    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    }

    next_object_number = 5
    if logo_asset is not None:
        logo_stream, logo_width, logo_height = logo_asset
        objects[5] = logo_stream
        logo_info = (logo_width, logo_height)
        next_object_number = 6

    page_object_numbers: list[int] = []
    body_top_y = PAGE_HEIGHT - TOP_BAND_HEIGHT - INFO_BAND_HEIGHT - 26
    summary_top_y = PAGE_HEIGHT - TOP_BAND_HEIGHT - INFO_BAND_HEIGHT - 32
    body_width = PAGE_WIDTH - (MARGIN * 2)

    for index, body in enumerate(page_bodies):
        page_number = index + 1
        content_object_number = next_object_number
        page_object_number = next_object_number + 1
        next_object_number += 2

        page_object_numbers.append(page_object_number)

        commands: list[str] = []
        _draw_header(commands, periodo_label, fecha_inicio, fecha_fin, generated_at, page_number, len(page_bodies), logo_info)
        current_body_top_y = body_top_y
        if page_number == 1:
            current_body_top_y = _draw_summary_cards(commands, report, summary_top_y)
        _draw_body_lines(commands, body, MARGIN, current_body_top_y, body_width)
        _draw_footer(commands, page_number, len(page_bodies))

        stream = _build_content_stream(commands)
        objects[content_object_number] = (
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )

        resources = b"<< /ProcSet [/PDF /Text /ImageC] /Font << /F1 3 0 R /F2 4 0 R >>"
        if logo_info is not None:
            resources += b" /XObject << /Im1 5 0 R >>"
        resources += b" >>"

        objects[page_object_number] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "
            + str(PAGE_WIDTH).encode("ascii")
            + b" "
            + str(PAGE_HEIGHT).encode("ascii")
            + b"] /Resources "
            + resources
            + b" /Contents "
            + str(content_object_number).encode("ascii")
            + b" 0 R >>"
        )

    kids = " ".join(f"{number} 0 R" for number in page_object_numbers).encode("ascii")
    objects[2] = b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(page_object_numbers)).encode("ascii") + b" >>"

    return _build_pdf_bytes(objects)
