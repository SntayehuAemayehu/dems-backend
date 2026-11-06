# dems-backend/certificates/views.py
from django.http import FileResponse, Http404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Certificate
from .serializers import CertificateSerializer
from services.certificate_service import certificate_service


class MyCertificatesView(APIView):
    """GET /api/certificates/ -> list the logged-in student's certificates."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        certs = Certificate.objects.filter(student__user=request.user)
        serializer = CertificateSerializer(certs, many=True, context={'request': request})
        return Response(serializer.data)


class CertificateDownloadView(APIView):
    """GET /api/certificates/<certification_id>/download/ -> PDF."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, certification_id):
        try:
            cert = Certificate.objects.get(
                certification_id=certification_id,
                student__user=request.user,
            )
        except Certificate.DoesNotExist:
            raise Http404("Certificate not found")

        return FileResponse(
            cert.pdf_file.open('rb'),
            as_attachment=True,
            filename=f"certificate_{cert.course.course_code}.pdf",
            content_type='application/pdf',
        )


class CertificateVerifyView(APIView):
    """GET /api/certificates/verify/<certification_id>/ -> {valid: bool}"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, certification_id):
        result = certificate_service.verify_certificate(certification_id)
        return Response(result)