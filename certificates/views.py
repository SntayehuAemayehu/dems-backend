# dems-backend/certificates/views.py
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Certificate
from .serializers import CertificateSerializer
from services.certificate_service import certificate_service
from courses.models import Enrollment
from django.utils import timezone


class MyCertificatesView(APIView):
    """GET /api/certificates/ -> list the logged-in student's certificates."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != 'STUDENT':
            return Response({'error': 'Only students can view their certificates'}, status=403)
        certs = Certificate.objects.filter(student__user=request.user, is_published=True)
        serializer = CertificateSerializer(certs, many=True, context={'request': request})
        return Response(serializer.data)


class RegistrarGenerateCertificateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, enrollment_id):
        if request.user.role not in ('REGISTRAR', 'ADMIN'):
            return Response({'error': 'Only the Registrar can issue certificates'}, status=403)

        try:
            enrollment = Enrollment.objects.select_related(
                'student__user', 'course'
            ).get(pk=enrollment_id)
        except Enrollment.DoesNotExist:
            raise Http404("Enrollment not found")

        if not enrollment.result_sent_to_registrar:
            return Response(
                {'error': 'The Department Head must send this result to the Registrar first'},
                status=400,
            )
        if enrollment.status != 'COMPLETED':
            return Response({'error': 'Only completed course results can be certified'}, status=400)

        certificate = Certificate.objects.filter(
            student=enrollment.student,
            course=enrollment.course,
        ).first()
        if certificate and certificate.is_published:
            serializer = CertificateSerializer(certificate, context={'request': request})
            return Response(serializer.data)

        result = certificate_service.generate_course_certificate(enrollment.student, enrollment)
        if certificate is None:
            certificate = Certificate(
                student=enrollment.student,
                enrollment=enrollment,
                course=enrollment.course,
                certification_id=result['certification_id'],
            )
        else:
            certificate.certification_id = result['certification_id']
        certificate.issued_at = timezone.now()
        certificate.is_published = True
        certificate.pdf_file.save(result['filename'], ContentFile(result['pdf']), save=False)
        certificate.save()

        serializer = CertificateSerializer(certificate, context={'request': request})
        return Response(serializer.data, status=201)


class CertificateDownloadView(APIView):
    """GET /api/certificates/<certification_id>/download/ -> PDF."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, certification_id):
        try:
            cert = Certificate.objects.get(
                certification_id=certification_id,
                student__user=request.user,
                is_published=True,
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
        certificate = Certificate.objects.filter(
            certification_id=certification_id,
            is_published=True,
        ).first()
        if certificate is None:
            return Response({'valid': False, 'message': 'Certificate not found'})
        result = certificate_service.verify_certificate(certification_id)
        return Response(result)