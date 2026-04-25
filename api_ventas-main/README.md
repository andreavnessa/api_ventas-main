🛒 API de Ventas
Sistema de gestión de productos, clientes y ventas desarrollado con Django REST Framework.
Incluye autenticación JWT, roles de usuario (Admin/Vendedor/Lector), CRUD completo con permisos por rol, filtros avanzados, paginación, testing automatizado y documentación Swagger/OpenAPI.

🚀 Características principales
- **CRUD completo** de **Clientes**, **Productos** y **Ventas** con permisos por rol.
- **Autenticación JWT** con access y refresh tokens.
- **Sistema de roles y permisos**:
  - **Admin**: CRUD completo + gestión del sistema
  - **Vendedor**: Lectura + creación de ventas (su función principal)
  - **Lector**: Solo lectura (supervisión)
- **Arquitectura dual de endpoints**:
  - **Endpoints públicos**: `/api/clientes/`, `/api/productos/`, `/api/ventas/` (lectura)
  - **Endpoints de Admin**: `/api/admin/clientes/`, `/api/admin/productos/`, `/api/admin/ventas/` (CRUD completo)
- **Endpoint especializado de ventas**: `/api/ventas/crear/` con validación de stock
- **Paginación configurable** (10 items por página por defecto).
- **Filtros avanzados**:
  - Clientes por nombre.
  - Productos por rango de precio y stock.
  - Ventas por fecha y cliente.
- **Validaciones robustas** con mensajes claros de error.
- **Ordenamiento** en todos los endpoints.
- **Transacciones atómicas** en creación de ventas.
- **Testing automatizado** con Django TestCase.
- **Documentación API** con Swagger/OpenAPI.

 
📂 Estructura del proyecto
api_ventas/
├── api_ventas/          # Configuración principal de Django
│   ├── settings.py     # Configuración DRF, JWT y base de datos
│   └── urls.py         # URLs principales y endpoints JWT
├── core/               # App auxiliar
│   ├── views.py        # Health check endpoint
│   └── urls.py         # URLs de core
├── ventas/             # App principal del negocio
│   ├── models.py       # Cliente, Producto, Venta, DetalleVenta
│   ├── serializers.py  # Serializers con validaciones
│   ├── views.py        # ViewSets con permisos y filtros
│   ├── urls.py         # URLs de la API
│   ├── filters.py      # Filtros avanzados
│   ├── pagination.py   # Paginación personalizada
│   ├── permissions.py  # Roles y permisos personalizados
│   └── tests.py        # Testing automatizado
├── create_users.py     # Script para crear usuarios de prueba
├── requirements.txt    # Dependencias del proyecto
└── README.md          # Documentación



🔑 Instalación y uso
# Clonar repositorio
git clone https://github.com/adrianlugo/api_ventas.git
cd api_ventas

# Crear entorno virtual
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# Instalar dependencias
pip install -r requirements.txt

# Migraciones
python manage.py migrate

# Crear superusuario (Admin)
python manage.py createsuperuser

# Opcional: Crear usuarios de prueba automáticamente
python create_users.py

# Ejecutar servidor
python manage.py runserver



📡 Endpoints de la API
| Método | Endpoint | Descripción | Permisos |
|--------|----------|-------------|----------|
| POST | `/api/token/` | Obtener tokens JWT | Público |
| POST | `/api/token/refresh/` | Refrescar access token | Público |
| GET | `/api/health/` | Health check | Público |
| GET | `/api/docs/` | Documentación Swagger/OpenAPI | Público |
| | | | |
| **Endpoints Públicos (lectura)** | | | |
| GET | `/api/clientes/` | Listar clientes | Admin/Vendedor/Lector |
| GET | `/api/productos/` | Listar productos | Admin/Vendedor/Lector |
| GET | `/api/ventas/` | Listar ventas | Admin/Vendedor/Lector |
| POST | `/api/ventas/crear/` | Crear venta completa | Admin/Vendedor |
| | | | |
| **Endpoints de Admin (CRUD completo)** | | | |
| GET/POST | `/api/admin/clientes/` | Listar/Crear clientes | Admin |
| GET/PUT/DELETE | `/api/admin/clientes/{id}/` | Ver/Actualizar/Eliminar cliente | Admin |
| GET/POST | `/api/admin/productos/` | Listar/Crear productos | Admin |
| GET/PUT/DELETE | `/api/admin/productos/{id}/` | Ver/Actualizar/Eliminar producto | Admin |
| GET/POST | `/api/admin/ventas/` | Listar/Crear ventas básicas | Admin |
| GET/PUT/DELETE | `/api/admin/ventas/{id}/` | Ver/Actualizar/Eliminar venta | Admin |

**Parámetros de consulta:**
- `?page=2` - Paginación
- `?page_size=20` - Tamaño de página
- `?ordering=nombre` - Ordenamiento
- `?nombre=Juan` - Filtro clientes
- `?precio_min=100&precio_max=500` - Filtro productos
- `?fecha=2026-01-26` - Filtro ventas 



🧪 Ejemplos de uso

### 1. Autenticación
**Login:**
```bash
POST /api/token/
Content-Type: application/json

{
  "username": "admin",
  "password": "tu_password"
}
```

**Respuesta:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Usar el token:**
```bash
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

### 2. Crear venta completa
```bash
POST /api/ventas/crear/
Content-Type: application/json
Authorization: Bearer <access_token>

{
  "cliente": 1,
  "detalles": [
    {"producto": 2, "cantidad": 3},
    {"producto": 5, "cantidad": 1}
  ]
}
```

**Respuesta:**
```json
{
  "id": 10,
  "cliente": 1,
  "fecha": "2026-01-26T13:30:00Z",
  "total": "150.00",
  "detalles": [
    {
      "id": 1,
      "producto": 2,
      "producto_nombre": "Laptop",
      "cantidad": 3,
      "subtotal": "90.00"
    },
    {
      "id": 2,
      "producto": 5,
      "producto_nombre": "Mouse",
      "cantidad": 1,
      "subtotal": "60.00"
    }
  ]
}
```

### 3. Filtrar productos
```bash
GET /api/productos/?precio_min=100&precio_max=500&ordering=precio
Authorization: Bearer <access_token>
```

### 4. Paginación
```bash
GET /api/clientes/?page=2&page_size=5
Authorization: Bearer <access_token>
```



🔧 Tecnologías utilizadas
- **Backend**: Django 6.0.1
- **API Framework**: Django REST Framework 3.16.1
- **Autenticación**: djangorestframework-simplejwt 5.5.1
- **Filtros**: django-filter 25.2
- **Documentación**: drf-spectacular 0.29.0 (Swagger/OpenAPI)
- **Base de datos**: SQLite (desarrollo)
- **Python**: 3.13+

📊 Características técnicas destacadas
- **Arquitectura RESTful** con ViewSets y Serializers
- **Sistema de permisos personalizado** con roles por grupos
- **Validaciones a nivel de modelo y serializer**
- **Transacciones atómicas** en creación de ventas
- **Optimización de queries** con select_related y prefetch_related
- **Manejo de errores** con códigos HTTP adecuados
- **Testing** con Django TestCase

🚀 Despliegue
- **Entorno de desarrollo**: SQLite + runserver
- **Producción recomendada**: PostgreSQL + Gunicorn + Nginx
- **Plataformas sugeridas**: Heroku, Railway, Render, Vercel

📊 Mejoras futuras
- **Dashboard de estadísticas** (ventas por mes, top productos/clientes)
- **Testing avanzado** con pytest y coverage
- **Cache con Redis** para endpoints frecuentes
- **WebSocket** para actualizaciones en tiempo real
- **Exportación** de reportes (PDF, Excel)
- **Integración** con pasarelas de pago
- **Docker** para containerización

👨‍💻 Autor
**Adrian Lugo** – Django Developer
Proyecto creado para portafolio profesional.

📧 Contacto
- GitHub: [adrianlugo](https://github.com/adrianlugo)
- Email: adrianlugofrontela@gmail.com

📄 Licencia
MIT License - Libre uso y modificación


