from django.test import TestCase

from accounts.models import StudentProfile, User
from courses.models import Course, Enrollment
from payments.models import PaymentProof
from payments.views import payment_submission_block_reason


class PaymentSubmissionEligibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='student@example.com',
            password='test-password',
            full_name='Test Student',
        )
        self.student = StudentProfile.objects.create(
            user=self.user,
            payment_status='VERIFIED',
        )
        self.payment = PaymentProof.objects.create(
            student=self.student,
            transaction_id='verified-payment',
            transaction_date='2026-01-01',
            status='VERIFIED',
        )
        self.course = Course.objects.create(
            course_code='TEST101',
            title='Test Course',
        )

    def test_verified_payment_blocks_submission_regardless_of_enrollment(self):
        self.assertIsNotNone(payment_submission_block_reason(self.student))

        Enrollment.objects.create(
            student=self.student,
            course=self.course,
            status='ACTIVE',
        )
        self.assertIsNotNone(payment_submission_block_reason(self.student))

        self.student.payment_status = 'PENDING'
        self.student.save(update_fields=['payment_status'])
        self.assertIsNotNone(payment_submission_block_reason(self.student))

    def test_pending_proof_blocks_submission_but_rejected_proof_does_not(self):
        self.student.payment_status = 'PENDING'
        self.student.save(update_fields=['payment_status'])
        self.payment.status = 'REJECTED'
        self.payment.save(update_fields=['status'])
        self.assertIsNone(payment_submission_block_reason(self.student))

        self.payment.status = 'PENDING'
        self.payment.save(update_fields=['status'])
        self.assertIsNotNone(payment_submission_block_reason(self.student))
