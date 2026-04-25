from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='activo',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='producto',
            name='categoria',
            field=models.CharField(default='General', max_length=100),
        ),
        migrations.AddField(
            model_name='producto',
            name='descripcion',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='producto',
            name='sku',
            field=models.CharField(default='', max_length=50, unique=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='producto',
            name='stock_minimo',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name='MovimientoInventario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('entrada', 'Entrada'), ('ajuste', 'Ajuste')], default='entrada', max_length=20)),
                ('cantidad', models.PositiveIntegerField()),
                ('observacion', models.CharField(blank=True, max_length=255)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='movimientos', to='ventas.producto')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-fecha'],
            },
        ),
    ]
