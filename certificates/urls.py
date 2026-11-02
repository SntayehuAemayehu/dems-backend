# dems-backend/certificates/urls.py
from django.urls import path
from .views import MyCertificatesView, CertificateDownloadView, CertificateVerifyView

urlpatterns = [
    path('', MyCertificatesView.as_view(), name='my-certificates'),
    path('<str:certification_id>/download/', CertificateDownloadView.as_view(), name='certificate-download'),
    path('verify/<str:certification_id>/', CertificateVerifyView.as_view(), name='certificate-verify'),
]