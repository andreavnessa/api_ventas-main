from calendar import monthrange
from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group, User
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import Count, F, Sum
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView, View
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .fiscal import calculate_invoice_amounts, calculate_line_amounts, get_current_fiscal_values, to_money
from .filters import ClienteFilter, ProductoFilter, VentaFilter
from .forms import PagoVentaForm, PrecioForm, ProductoForm, StockCargaForm, VentaForm, VentaItemFormSet
from .models import Cliente, DetalleVenta, MovimientoInventario, Producto, Venta
from .pagination import StandardResultsSetPagination
from .pdf_utils import build_quincenal_report_pdf
from .permissions import AdminVendedorLecturaMixin, IsAdmin, IsAdminOrVendedor
from .serializers import ClienteSerializer, ProductoSerializer, UserSerializer, VentaCreateSerializer, VentaSerializer


def _get_current_fiscal_values():
    fiscal_values = get_current_fiscal_values()
    return {
        'tasa_dolar': to_money(fiscal_values['tasa_dolar']),
        'iva_porcentaje': to_money(fiscal_values['iva_porcentaje']),
    }


MESES_ES = [
    'enero',
    'febrero',
    'marzo',
    'abril',
    'mayo',
    'junio',
    'julio',
    'agosto',
    'septiembre',
    'octubre',
    'noviembre',
    'diciembre',
]


def _get_quincena_range(year=None, month=None, quincena=None):
    today = timezone.localdate()

    try:
        year = int(year) if year is not None else today.year
        month = int(month) if month is not None else today.month
    except (TypeError, ValueError):
        year = today.year
        month = today.month

    if month < 1 or month > 12:
        year = today.year
        month = today.month

    if quincena in (1, 2, '1', '2'):
        quincena = int(quincena)
    else:
        quincena = 1 if year == today.year and month == today.month and today.day <= 15 else 2

    if quincena == 1:
        fecha_inicio = date(year, month, 1)
        fecha_fin = date(year, month, 15)
    else:
        fecha_inicio = date(year, month, 16)
        fecha_fin = date(year, month, monthrange(year, month)[1])

    return year, month, quincena, fecha_inicio, fecha_fin


def _shift_quincena(year, month, quincena, steps):
    for _ in range(abs(steps)):
        if steps > 0:
            if quincena == 1:
                quincena = 2
            else:
                quincena = 1
                if month == 12:
                    year += 1
                    month = 1
                else:
                    month += 1
        else:
            if quincena == 2:
                quincena = 1
            else:
                quincena = 2
                if month == 1:
                    year -= 1
                    month = 12
                else:
                    month -= 1
    return year, month, quincena


def _build_quincenal_report_context(request):
    year, month, quincena, fecha_inicio, fecha_fin = _get_quincena_range(
        request.GET.get('anio') or request.GET.get('year'),
        request.GET.get('mes') or request.GET.get('month'),
        request.GET.get('quincena'),
    )

    ventas_qs = (
        Venta.objects.filter(fecha__date__range=(fecha_inicio, fecha_fin))
        .select_related('cliente')
        .prefetch_related('detalles__producto')
        .order_by('-fecha')
    )
    ventas_pagadas_qs = ventas_qs.filter(estado_pago=Venta.ESTADO_PAGADO)
    resumen_financiero = ventas_pagadas_qs.aggregate(
        subtotal_usd=Sum('subtotal_usd'),
        subtotal_bs=Sum('subtotal_bs'),
        iva_usd=Sum('iva_usd'),
        iva_bs=Sum('iva_bs'),
        total_usd=Sum('total'),
        total_bs=Sum('total_bs'),
    )
    resumen_facturado = ventas_qs.aggregate(
        total_usd=Sum('total'),
        total_bs=Sum('total_bs'),
    )

    ventas_detalladas = []
    total_unidades_vendidas = 0

    for venta in ventas_qs:
        unidades = sum(detalle.cantidad for detalle in venta.detalles.all())
        total_unidades_vendidas += unidades
        ventas_detalladas.append({
            'venta': venta,
            'unidades': unidades,
            'detalles': list(venta.detalles.all()),
        })

    medios_pago = list(
        ventas_pagadas_qs.values('metodo_pago')
        .annotate(
            cantidad=Count('id'),
            total_usd=Sum('total'),
            total_bs=Sum('total_bs'),
        )
        .order_by('-cantidad')
    )

    productos_top = list(
        DetalleVenta.objects.filter(venta__fecha__date__range=(fecha_inicio, fecha_fin))
        .values('producto__id', 'producto__nombre', 'producto__sku')
        .annotate(
            unidades=Sum('cantidad'),
            subtotal_usd=Sum('subtotal'),
        )
        .order_by('-unidades')[:5]
    )

    ventas_registradas = ventas_qs.count()
    ventas_pagadas = ventas_pagadas_qs.count()
    ventas_pendientes = ventas_qs.filter(estado_pago=Venta.ESTADO_PENDIENTE).count()
    ventas_canceladas = ventas_qs.filter(estado_pago=Venta.ESTADO_CANCELADO).count()

    total_cobrado_usd = to_money(resumen_financiero['total_usd'] or 0)
    total_cobrado_bs = to_money(resumen_financiero['total_bs'] or 0)
    subtotal_usd = to_money(resumen_financiero['subtotal_usd'] or 0)
    subtotal_bs = to_money(resumen_financiero['subtotal_bs'] or 0)
    iva_usd = to_money(resumen_financiero['iva_usd'] or 0)
    iva_bs = to_money(resumen_financiero['iva_bs'] or 0)
    total_facturado_usd = to_money(resumen_facturado['total_usd'] or 0)
    total_facturado_bs = to_money(resumen_facturado['total_bs'] or 0)
    ticket_promedio_usd = to_money(total_cobrado_usd / ventas_pagadas) if ventas_pagadas else to_money(0)
    ticket_promedio_bs = to_money(total_cobrado_bs / ventas_pagadas) if ventas_pagadas else to_money(0)

    periodo_label = f'Quincena {quincena} de {MESES_ES[month - 1].capitalize()} {year}'

    prev_year, prev_month, prev_quincena = _shift_quincena(year, month, quincena, -1)
    next_year, next_month, next_quincena = _shift_quincena(year, month, quincena, 1)

    return {
        'periodo': {
            'anio': year,
            'mes': month,
            'quincena': quincena,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'label': periodo_label,
        },
        'periodo_anterior': {
            'anio': prev_year,
            'mes': prev_month,
            'quincena': prev_quincena,
        },
        'periodo_siguiente': {
            'anio': next_year,
            'mes': next_month,
            'quincena': next_quincena,
        },
        'resumen': {
            'ventas_registradas': ventas_registradas,
            'ventas_pagadas': ventas_pagadas,
            'ventas_pendientes': ventas_pendientes,
            'ventas_canceladas': ventas_canceladas,
            'total_unidades_vendidas': total_unidades_vendidas,
            'subtotal_usd': subtotal_usd,
            'subtotal_bs': subtotal_bs,
            'iva_usd': iva_usd,
            'iva_bs': iva_bs,
            'total_cobrado_usd': total_cobrado_usd,
            'total_cobrado_bs': total_cobrado_bs,
            'total_facturado_usd': total_facturado_usd,
            'total_facturado_bs': total_facturado_bs,
            'ticket_promedio_usd': ticket_promedio_usd,
            'ticket_promedio_bs': ticket_promedio_bs,
        },
        'ventas_detalladas': ventas_detalladas,
        'medios_pago': medios_pago,
        'productos_top': productos_top,
    }


class ReporteQuincenalView(LoginRequiredMixin, TemplateView):
    template_name = 'ventas/reporte_quincenal.html'

    def get(self, request, *args, **kwargs):
        if request.GET.get('formato') == 'pdf' or request.GET.get('pdf') in ('1', 'true', 'True'):
            context = self.get_context_data()
            pdf_bytes = build_quincenal_report_pdf(context)
            periodo = context['periodo']
            filename = f"reporte_quincenal_{periodo['anio']}_{periodo['mes']:02d}_q{periodo['quincena']}.pdf"
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_build_quincenal_report_context(self.request))
        return context


class ReporteQuincenalPDFView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        context = _build_quincenal_report_context(request)
        pdf_bytes = build_quincenal_report_pdf(context)
        periodo = context['periodo']
        filename = f"reporte_quincenal_{periodo['anio']}_{periodo['mes']:02d}_q{periodo['quincena']}.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


# ViewSets para lectura (Vendedor y Lector)
class ClienteViewSet(AdminVendedorLecturaMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ClienteFilter
    ordering_fields = ['nombre', 'id']
    ordering = ['id']


class ProductoViewSet(AdminVendedorLecturaMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductoFilter
    ordering_fields = ['precio', 'nombre', 'stock']
    ordering = ['id']


class VentaViewSet(AdminVendedorLecturaMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Venta.objects.select_related('cliente').prefetch_related('detalles__producto')
    serializer_class = VentaSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = VentaFilter
    ordering_fields = ['fecha', 'total']
    ordering = ['-fecha']


# ViewSets para Admin (CRUD completo)
class AdminClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all().order_by('id')
    serializer_class = ClienteSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ClienteFilter
    ordering_fields = ['nombre', 'id']
    ordering = ['id']
    permission_classes = [IsAuthenticated, IsAdmin]


class AdminProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all().order_by('id')
    serializer_class = ProductoSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductoFilter
    ordering_fields = ['precio', 'nombre', 'stock']
    ordering = ['id']
    permission_classes = [IsAuthenticated, IsAdmin]


class AdminVentaViewSet(viewsets.ModelViewSet):
    queryset = Venta.objects.select_related('cliente').prefetch_related('detalles__producto')
    serializer_class = VentaSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = VentaFilter
    ordering_fields = ['fecha', 'total']
    ordering = ['-fecha']
    permission_classes = [IsAuthenticated, IsAdmin]


class RegistrarVentaView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrVendedor]
    serializer_class = VentaCreateSerializer

    def post(self, request):
        serializer = VentaCreateSerializer(data=request.data)

        if serializer.is_valid():
            venta = serializer.save()
            return Response(VentaSerializer(venta).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Usuario',
            'autofocus': 'autofocus',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Contraseña',
            'autocomplete': 'current-password',
        })


class UserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        groups = [group.name for group in user.groups.all()]
        data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'groups': groups
        }
        return Response(data)


class AdminUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]

    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        user = self.get_object()
        new_password = 'temp123'
        user.set_password(new_password)
        user.save()
        return Response({'message': 'Contraseña reseteada exitosamente', 'new_password': new_password})


class DashboardTemplateView(LoginRequiredMixin, TemplateView):
    template_name = 'ventas/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ventas = Venta.objects.all()
        productos = Producto.objects.all()

        context['ventas_hoy_total'] = ventas.filter(estado_pago=Venta.ESTADO_PAGADO).count()
        total_ingresos = ventas.filter(estado_pago=Venta.ESTADO_PAGADO).aggregate(total=Sum('total'))['total'] or 0
        context['ingresos_totales'] = to_money(total_ingresos)
        context['productos_activos'] = productos.filter(activo=True).count()
        context['productos_agotados'] = productos.filter(stock=0, activo=True).count()
        context['stock_bajo'] = productos.filter(stock__lte=F('stock_minimo'), activo=True).count()
        context['clientes_total'] = Cliente.objects.count()
        context['ultimas_ventas'] = ventas.select_related('cliente').order_by('-fecha')[:5]
        return context


class RegistroTemplateView(TemplateView):
    template_name = 'ventas/registro.html'


class UsersTemplateView(TemplateView):
    template_name = 'ventas/users.html'


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = CustomLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy('home')


# Vistas web
class HomeView(LoginRequiredMixin, TemplateView):
    template_name = 'ventas/home.html'

    def get(self, request, *args, **kwargs):
        return redirect('dashboard')


class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'ventas/cliente_list.html'
    ordering = ['id']


class ClienteDetailView(LoginRequiredMixin, DetailView):
    model = Cliente
    template_name = 'ventas/cliente_detail.html'


class ClienteCreateView(LoginRequiredMixin, CreateView):
    model = Cliente
    template_name = 'ventas/cliente_form.html'
    fields = ['nombre', 'cedula', 'email', 'telefono']
    success_url = reverse_lazy('cliente_list')


class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    template_name = 'ventas/cliente_form.html'
    fields = ['nombre', 'cedula', 'email', 'telefono']
    success_url = reverse_lazy('cliente_list')


class ClienteDeleteView(LoginRequiredMixin, DeleteView):
    model = Cliente
    template_name = 'ventas/cliente_confirm_delete.html'
    success_url = reverse_lazy('cliente_list')


class ProductoListView(LoginRequiredMixin, ListView):
    model = Producto
    template_name = 'ventas/producto_list.html'
    ordering = ['id']

    def get_queryset(self):
        queryset = super().get_queryset()
        filtro = self.request.GET.get('filtro')

        if filtro == 'agotados':
            queryset = queryset.filter(stock=0)
        elif filtro == 'stock_bajo':
            queryset = queryset.filter(stock__lte=F('stock_minimo'))

        return queryset.order_by('id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agotados_count'] = Producto.objects.filter(stock=0).count()
        context['stock_bajo_count'] = Producto.objects.filter(stock__lte=F('stock_minimo')).count()
        context['filtro_actual'] = self.request.GET.get('filtro', '')
        return context


class ProductoDetailView(LoginRequiredMixin, DetailView):
    model = Producto
    template_name = 'ventas/producto_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['movimientos'] = self.object.movimientos.all()[:10]
        return context


class ProductoCreateView(LoginRequiredMixin, CreateView):
    model = Producto
    form_class = ProductoForm
    template_name = 'ventas/producto_form.html'
    success_url = reverse_lazy('producto_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.object.stock > 0:
            MovimientoInventario.objects.create(
                producto=self.object,
                tipo=MovimientoInventario.TIPO_ENTRADA,
                cantidad=self.object.stock,
                observacion='Stock inicial al registrar producto',
                usuario=self.request.user
            )
        messages.success(self.request, 'Producto creado correctamente.')
        return response


class ProductoUpdateView(LoginRequiredMixin, UpdateView):
    model = Producto
    form_class = ProductoForm
    template_name = 'ventas/producto_form.html'
    success_url = reverse_lazy('producto_list')

    def form_valid(self, form):
        messages.success(self.request, 'Producto actualizado correctamente.')
        return super().form_valid(form)


class ProductoDeleteView(LoginRequiredMixin, DeleteView):
    model = Producto
    template_name = 'ventas/producto_confirm_delete.html'
    success_url = reverse_lazy('producto_list')


class ProductoStockUpdateView(LoginRequiredMixin, TemplateView):
    template_name = 'ventas/producto_stock_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        producto_id = self.request.GET.get('producto')
        initial = {'producto': producto_id} if producto_id else None
        context['form'] = StockCargaForm(initial=initial)
        context['page_title'] = 'Cargar inventario'
        context['page_description'] = 'Suma unidades al stock actual de un producto existente.'
        return context

    def post(self, request, *args, **kwargs):
        form = StockCargaForm(request.POST)
        if form.is_valid():
            producto = form.cleaned_data['producto']
            cantidad = form.cleaned_data['cantidad']
            observacion = form.cleaned_data['observacion']

            producto.stock += cantidad
            producto.save(update_fields=['stock'])

            MovimientoInventario.objects.create(
                producto=producto,
                tipo=MovimientoInventario.TIPO_ENTRADA,
                cantidad=cantidad,
                observacion=observacion or 'Carga manual de inventario',
                usuario=request.user
            )
            messages.success(request, f'Se agregaron {cantidad} unidades al producto {producto.nombre}.')
            return redirect('producto_list')

        return self.render_to_response({
            'form': form,
            'page_title': 'Cargar inventario',
            'page_description': 'Suma unidades al stock actual de un producto existente.'
        })


class ProductoPrecioUpdateView(LoginRequiredMixin, UpdateView):
    model = Producto
    form_class = PrecioForm
    template_name = 'ventas/producto_price_form.html'
    success_url = reverse_lazy('producto_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['precio_actual'] = self.object.precio
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Precio actualizado correctamente.')
        return super().form_valid(form)


class ProductoAgotadoListView(ProductoListView):
    def get_queryset(self):
        return Producto.objects.filter(stock=0).order_by('id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filtro_actual'] = 'agotados'
        return context


class VentaCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'ventas/venta_form.html'
    session_key = 'venta_borrador'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = kwargs.get('form') or VentaForm(initial=self._get_initial_data())
        context['items_formset'] = kwargs.get('items_formset') or VentaItemFormSet(prefix='items', initial=self._get_items_initial_data())
        return context

    def _get_initial_data(self):
        venta_data = self.request.session.get(self.session_key, {})
        return {
            'cliente_nombre': venta_data.get('cliente_nombre', ''),
            'cliente_cedula': venta_data.get('cliente_cedula', ''),
            'cliente_email': venta_data.get('cliente_email', ''),
            'cliente_telefono': venta_data.get('cliente_telefono', ''),
        }

    def _get_items_initial_data(self):
        venta_data = self.request.session.get(self.session_key, {})
        items = venta_data.get('items', [])
        return [
            {
                'producto': item.get('producto_id'),
                'cantidad': item.get('cantidad'),
            }
            for item in items
        ]

    def post(self, request, *args, **kwargs):
        form = VentaForm(request.POST)
        items_formset = VentaItemFormSet(request.POST, prefix='items')

        if not form.is_valid() or not items_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, items_formset=items_formset))

        fiscal_values = _get_current_fiscal_values()
        tasa_dolar = fiscal_values['tasa_dolar']
        iva_porcentaje = fiscal_values['iva_porcentaje']
        items = []
        subtotal_total_usd = Decimal('0')

        for item_form in items_formset:
            if item_form.cleaned_data.get('DELETE'):
                continue

            producto = item_form.cleaned_data.get('producto')
            cantidad = item_form.cleaned_data.get('cantidad')

            if not producto and not cantidad:
                continue

            producto.refresh_from_db()
            if producto.stock < cantidad:
                item_form.add_error('cantidad', f'Stock insuficiente para {producto.nombre}. Disponible: {producto.stock}')
                return self.render_to_response(self.get_context_data(form=form, items_formset=items_formset))

            line_amounts = calculate_line_amounts(producto.precio, cantidad, tasa_dolar)
            subtotal_total_usd += line_amounts['subtotal_usd']
            items.append({
                'producto_id': producto.id,
                'producto_nombre': producto.nombre,
                'sku': producto.sku,
                'precio_usd': str(line_amounts['precio_unitario_usd']),
                'precio_bs': str(line_amounts['precio_unitario_bs']),
                'cantidad': cantidad,
                'subtotal_usd': str(line_amounts['subtotal_usd']),
                'subtotal_bs': str(line_amounts['subtotal_bs']),
            })

        if not items:
            messages.error(request, 'Debes agregar al menos un artículo a la venta.')
            return self.render_to_response(self.get_context_data(form=form, items_formset=items_formset))

        fiscal_totals = calculate_invoice_amounts(subtotal_total_usd, tasa_dolar, iva_porcentaje)

        request.session[self.session_key] = {
            'cliente_nombre': form.cleaned_data['cliente_nombre'],
            'cliente_cedula': form.cleaned_data['cliente_cedula'],
            'cliente_email': form.cleaned_data['cliente_email'],
            'cliente_telefono': form.cleaned_data['cliente_telefono'],
            'items': items,
            'tasa_dolar': str(tasa_dolar),
            'iva_porcentaje': str(iva_porcentaje),
            'subtotal_usd': str(fiscal_totals['subtotal_usd']),
            'subtotal_bs': str(fiscal_totals['subtotal_bs']),
            'iva_usd': str(fiscal_totals['iva_usd']),
            'iva_bs': str(fiscal_totals['iva_bs']),
            'total_usd': str(fiscal_totals['total_usd']),
            'total_bs': str(fiscal_totals['total_bs']),
            'subtotal': str(fiscal_totals['total_usd']),
        }
        request.session.modified = True

        return redirect('venta_pago')


class VentaPagoView(LoginRequiredMixin, TemplateView):
    template_name = 'ventas/venta_pago_form.html'
    session_key = 'venta_borrador'

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get(self.session_key):
            messages.warning(request, 'Primero debes completar los datos básicos de la venta.')
            return redirect('venta_create')
        return super().dispatch(request, *args, **kwargs)

    def _get_venta_data(self):
        return self.request.session.get(self.session_key, {})

    def _build_summary(self):
        venta_data = self._get_venta_data()
        fiscal_values = _get_current_fiscal_values()
        tasa_dolar = to_money(venta_data.get('tasa_dolar', fiscal_values['tasa_dolar']))
        iva_porcentaje = to_money(venta_data.get('iva_porcentaje', fiscal_values['iva_porcentaje']))
        subtotal_usd = to_money(venta_data.get('subtotal_usd', venta_data.get('subtotal', '0.00')))
        resumen_fiscal = calculate_invoice_amounts(subtotal_usd, tasa_dolar, iva_porcentaje)

        return {
            'cliente_nombre': venta_data.get('cliente_nombre', ''),
            'cliente_cedula': venta_data.get('cliente_cedula', ''),
            'cliente_email': venta_data.get('cliente_email', ''),
            'cliente_telefono': venta_data.get('cliente_telefono', ''),
            'items': venta_data.get('items', []),
            'tasa_dolar': tasa_dolar,
            'iva_porcentaje': iva_porcentaje,
            'subtotal_usd': resumen_fiscal['subtotal_usd'],
            'subtotal_bs': resumen_fiscal['subtotal_bs'],
            'iva_usd': resumen_fiscal['iva_usd'],
            'iva_bs': resumen_fiscal['iva_bs'],
            'total_usd': resumen_fiscal['total_usd'],
            'total_bs': resumen_fiscal['total_bs'],
            'subtotal': resumen_fiscal['total_usd'],
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = kwargs.get('form') or PagoVentaForm()
        context['resumen'] = self._build_summary()
        return context

    def post(self, request, *args, **kwargs):
        if 'cancelar' in request.POST:
            request.session.pop(self.session_key, None)
            request.session.modified = True
            messages.info(request, 'La venta fue cancelada antes de confirmar el pago.')
            return redirect('venta_list')

        form = PagoVentaForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        venta_data = self._get_venta_data()
        items = venta_data.get('items', [])
        fiscal_values = _get_current_fiscal_values()
        tasa_dolar = to_money(venta_data.get('tasa_dolar', fiscal_values['tasa_dolar']))
        iva_porcentaje = to_money(venta_data.get('iva_porcentaje', fiscal_values['iva_porcentaje']))
        subtotal_usd = to_money(venta_data.get('subtotal_usd', venta_data.get('subtotal', '0.00')))
        fiscal_totals = calculate_invoice_amounts(subtotal_usd, tasa_dolar, iva_porcentaje)

        with transaction.atomic():
            cliente_defaults = {
                'nombre': venta_data['cliente_nombre'],
                'cedula': venta_data['cliente_cedula'],
                'telefono': venta_data.get('cliente_telefono', ''),
            }
            cliente, creado = Cliente.objects.get_or_create(
                email=venta_data['cliente_email'],
                defaults=cliente_defaults
            )
            campos_actualizados = []
            if not creado:
                if cliente.nombre != venta_data['cliente_nombre']:
                    cliente.nombre = venta_data['cliente_nombre']
                    campos_actualizados.append('nombre')
                if cliente.cedula != venta_data['cliente_cedula']:
                    cliente.cedula = venta_data['cliente_cedula']
                    campos_actualizados.append('cedula')
                if cliente.telefono != venta_data.get('cliente_telefono', ''):
                    cliente.telefono = venta_data.get('cliente_telefono', '')
                    campos_actualizados.append('telefono')
                if campos_actualizados:
                    cliente.save(update_fields=campos_actualizados)

            venta = Venta.objects.create(
                cliente=cliente,
                tasa_dolar_aplicada=tasa_dolar,
                iva_porcentaje_aplicado=iva_porcentaje,
                subtotal_usd=fiscal_totals['subtotal_usd'],
                subtotal_bs=fiscal_totals['subtotal_bs'],
                iva_usd=fiscal_totals['iva_usd'],
                iva_bs=fiscal_totals['iva_bs'],
                total=fiscal_totals['total_usd'],
                total_bs=fiscal_totals['total_bs'],
                metodo_pago=form.cleaned_data['metodo_pago'],
                referencia_pago=form.cleaned_data['referencia_pago'],
                estado_pago=Venta.ESTADO_PAGADO
            )

            for item in items:
                producto = get_object_or_404(Producto, pk=item['producto_id'])
                cantidad = int(item['cantidad'])
                producto.refresh_from_db()

                if producto.stock < cantidad:
                    messages.error(request, f'Stock insuficiente para {producto.nombre}. Disponible: {producto.stock}')
                    raise transaction.TransactionManagementError('Stock insuficiente al confirmar la venta.')

                line_amounts = calculate_line_amounts(producto.precio, cantidad, tasa_dolar)

                DetalleVenta.objects.create(
                    venta=venta,
                    producto=producto,
                    cantidad=cantidad,
                    subtotal=line_amounts['subtotal_usd']
                )

                producto.stock -= cantidad
                producto.save(update_fields=['stock'])

                MovimientoInventario.objects.create(
                    producto=producto,
                    tipo=MovimientoInventario.TIPO_SALIDA_VENTA,
                    cantidad=cantidad,
                    observacion=f'Salida por venta #{venta.id}',
                    usuario=request.user
                )

        request.session.pop(self.session_key, None)
        request.session.modified = True
        messages.success(request, f'Pago confirmado y venta registrada correctamente para {cliente.nombre}.')
        return redirect('venta_detail', pk=venta.pk)


class VentaListView(LoginRequiredMixin, ListView):
    model = Venta
    template_name = 'ventas/venta_list.html'
    ordering = ['-fecha']


class VentaDetailView(LoginRequiredMixin, DetailView):
    model = Venta
    template_name = 'ventas/venta_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fiscal_values = _get_current_fiscal_values()
        tasa_dolar = to_money(self.object.tasa_dolar_aplicada or fiscal_values['tasa_dolar'])
        iva_porcentaje = to_money(self.object.iva_porcentaje_aplicado or fiscal_values['iva_porcentaje'])

        if self.object.subtotal_usd and self.object.total_bs:
            resumen_fiscal = {
                'tasa_dolar': tasa_dolar,
                'iva_porcentaje': iva_porcentaje,
                'subtotal_usd': self.object.subtotal_usd,
                'subtotal_bs': self.object.subtotal_bs,
                'iva_usd': self.object.iva_usd,
                'iva_bs': self.object.iva_bs,
                'total_usd': self.object.total,
                'total_bs': self.object.total_bs,
            }
        else:
            subtotal_usd = self.object.total
            subtotal_bs = to_money(subtotal_usd * tasa_dolar)
            resumen_fiscal = {
                'tasa_dolar': tasa_dolar,
                'iva_porcentaje': iva_porcentaje,
                'subtotal_usd': subtotal_usd,
                'subtotal_bs': subtotal_bs,
                'iva_usd': to_money(0),
                'iva_bs': to_money(0),
                'total_usd': self.object.total,
                'total_bs': subtotal_bs,
            }

        context['resumen_fiscal'] = resumen_fiscal
        context['detalles_fiscales'] = [
            {
                'detalle': detalle,
                **calculate_line_amounts(detalle.producto.precio, detalle.cantidad, tasa_dolar),
            }
            for detalle in self.object.detalles.select_related('producto').all()
        ]
        context['unidades_totales'] = sum(detalle.cantidad for detalle in self.object.detalles.all())
        return context
