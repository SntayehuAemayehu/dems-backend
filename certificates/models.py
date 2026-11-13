# dems-backend/certificates/models.py
from django.db import models


class Certificate(models.Model):
    """A generated course-completion certificate for a student."""

    student = models.ForeignKey(
        'accounts.StudentProfile',
        on_delete=models.CASCADE,
        related_name='certificates',
    )
    enrollment = models.ForeignKey(
        'courses.Enrollment',
        on_delete=models.CASCADE,
        related_name='certificates',
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='certificates',
    )
    certification_id = models.CharField(max_length=64, unique=True, db_index=True)
    pdf_file = models.FileField(upload_to='certificates/')
    is_published = models.BooleanField(default=False)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issued_at']
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.certification_id} - {self.student} - {self.course.course_code}"