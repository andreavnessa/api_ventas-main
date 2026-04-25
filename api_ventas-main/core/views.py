from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class HealthCheckView(APIView):
    """
    Endpoint para verificar el estado de la API
    - GET /api/health/ → Estado del sistema
    """
    serializer_class = None  # Para Swagger/OpenAPI
    
    def get(self, request):
        return Response({"status": "ok", "message": "API funcionando"})