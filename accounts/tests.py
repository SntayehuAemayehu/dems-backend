from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from unittest.mock import patch

from accounts.models import StudentProfile, User
from analytics.models import IDSequence, SystemConfig


class StudentDocumentReviewTests(TestCase):
    def setUp(self):
        self.student_user = User.objects.create_user(
            email='student@example.com',
            password='test-password',
            full_name='Test Student',
        )
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            payment_status='VERIFIED',
        )
        self.registrar = User.objects.create_user(
            email='registrar@example.com',
            password='test-password',
            full_name='Test Registrar',
            role='REGISTRAR',
        )
        self.client = APIClient()

    @patch('accounts.views.send_notification')
    def test_rejection_notifies_student_and_resubmission_reopens_review(self, notify):
        self.client.force_authenticate(self.registrar)
        endpoint = f'/api/auth/registrar/students/{self.student.id}/verify/'

        response = self.client.post(endpoint, {'action': 'reject'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.student.documents_status, 'NOT_SUBMITTED')

        response = self.client.post(
            endpoint,
            {'action': 'reject', 'reason': 'Transcript is missing'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.documents_status, 'REJECTED')
        self.assertEqual(self.student.documents_rejection_reason, 'Transcript is missing')
        notify.assert_called_once_with(
            recipient_user=self.student_user,
            title='❌ Documents Rejected',
            message='Your documents have been rejected. Reason: Transcript is missing. Please check and resubmit.',
            notification_type='SYSTEM_ALERT',
            link='/upload-documents',
        )

        self.client.force_authenticate(self.student_user)
        upload_url = '/api/auth/documents/upload/'
        response = self.client.post(
            upload_url,
            {'transcript': SimpleUploadedFile('transcript.pdf', b'pdf-content', content_type='application/pdf')},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.documents_status, 'PENDING')
        self.assertEqual(self.student.documents_rejection_reason, '')

        response = self.client.post(
            upload_url,
            {'transcript': SimpleUploadedFile('replacement.pdf', b'pdf-content', content_type='application/pdf')},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    @patch('accounts.views.send_notification')
    def test_approved_documents_cannot_be_uploaded_again(self, _notify):
        self.client.force_authenticate(self.registrar)
        response = self.client.post(
            f'/api/auth/registrar/students/{self.student.id}/verify/',
            {'action': 'verify'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)

        self.client.force_authenticate(self.student_user)
        response = self.client.post(
            '/api/auth/documents/upload/',
            {'transcript': SimpleUploadedFile('transcript.pdf', b'pdf-content', content_type='application/pdf')},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    @patch('accounts.views.send_notification', side_effect=RuntimeError('notification unavailable'))
    def test_generate_student_id_handles_existing_id_collision(self, notify):
        year = timezone.now().year
        prefix = 'STU'
        format_string = '{prefix}{year}{seq_padded}'
        SystemConfig.objects.update_or_create(
            key='student_id_prefix',
            defaults={'value': prefix},
        )
        SystemConfig.objects.update_or_create(
            key='student_id_format',
            defaults={'value': format_string},
        )
        IDSequence.objects.create(prefix=prefix, year=year, last_number=2)

        existing_user = User.objects.create_user(
            email='existing@example.com',
            password='test-password',
            full_name='Existing Student',
        )
        StudentProfile.objects.create(
            user=existing_user,
            student_id=f'{prefix}{year}000003',
        )

        self.student.documents_verified = True
        self.student.save(update_fields=['documents_verified'])
        self.client.force_authenticate(self.registrar)

        response = self.client.post(
            f'/api/auth/registrar/students/{self.student.id}/generate-id/',
            format='json',
        )

        expected_id = f'{prefix}{year}000003-{self.student.id}'
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['student_id'], expected_id)
        self.student.refresh_from_db()
        self.assertEqual(self.student.student_id, expected_id)

        retry_response = self.client.post(
            f'/api/auth/registrar/students/{self.student.id}/generate-id/',
            format='json',
        )
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(retry_response.data['student_id'], expected_id)
        notify.assert_called_once()
