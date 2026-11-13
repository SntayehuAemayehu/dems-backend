# dems-backend/certificates/urls.py
from django.urls import path
from .views import (
    CertificateDownloadView,
    CertificateVerifyView,
    MyCertificatesView,
    RegistrarGenerateCertificateView,
)

urlpatterns = [
    path('', MyCertificatesView.as_view(), name='my-certificates'),
    path('enrollments/<int:enrollment_id>/generate/', RegistrarGenerateCertificateView.as_view(), name='registrar-generate-certificate'),
    path('<str:certification_id>/download/', CertificateDownloadView.as_view(), name='certificate-download'),
    path('verify/<str:certification_id>/', CertificateVerifyView.as_view(), name='certificate-verify'),
]