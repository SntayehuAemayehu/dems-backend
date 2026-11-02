# dems-backend/certificates/signals.py
import logging
from django.core.files.base import ContentFile
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from courses.models import Enrollment
from services.certificate_service import certificate_service
from .models import Certificate

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Enrollment)
def auto_generate_certificates_on_completion(sender, instance, created, **kwargs):
    """
    Fires on every Enrollment save. Generates a certificate immediately 
    if the status is ACTIVE or COMPLETED.
    """
    try:
        # 1. Check if the status is ACTIVE or COMPLETED
        status = str(getattr(instance, 'status', '')).upper()
        if status not in ['ACTIVE', 'COMPLETED']:
            return
            
        # 2. Check if the student already has a certificate for this course
        if Certificate.objects.filter(student=instance.student, course=instance.course).exists():
            return

        # 3. We will generate it right now. If grades are empty, we pass defaults so the PDF doesn't crash.
        if not instance.grade_letter or instance.grade_letter == 'NON':
            instance.grade_letter = 'N/A'
        if instance.percentage_score is None:
            instance.percentage_score = 0.0

        # 4. Generate the PDF
        result = certificate_service.generate_course_certificate(instance.student, instance)

        # 5. Save to database
        cert = Certificate(
            student=instance.student,
            enrollment=instance,
            course=instance.course,
            certification_id=result['certification_id'],
            issued_at=timezone.now(),
        )
        cert.pdf_file.save(
            result['filename'],
            ContentFile(result['pdf']),
            save=True,
        )
        logger.info(f"✅ Certificate generated successfully for {instance.student.student_id} - {instance.course.course_code}")
        
    except Exception as exc:
        logger.exception(f"❌ Certificate auto-generation failed: {exc}")