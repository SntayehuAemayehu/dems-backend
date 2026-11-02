# dems-backend/certificates/admin.py
from django.contrib import admin
from .models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('certification_id', 'student', 'course', 'issued_at')
    search_fields = ('certification_id', 'student__student_id', 'course__course_code')
    list_filter = ('issued_at',)
    readonly_fields = ('certification_id', 'issued_at')