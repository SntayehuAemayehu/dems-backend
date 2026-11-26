import tempfile
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Department, StudentProfile, User
from courses.models import Course
from exams.models import Exam, ExamAttempt
from proctoring.models import ProctorImage, ProctorLog
from proctoring.views import ProctorCaptureView, ReviewStudentsView


class ReviewStudentsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.test',
            password='test-password',
            full_name='Admin User',
            role='ADMIN',
        )
        self.student_user = User.objects.create_user(
            email='student@example.test',
            password='test-password',
            full_name='Student User',
            role='STUDENT',
        )
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            department='Computer Science',
        )
        self.factory = APIRequestFactory()

    def test_lists_students_by_department(self):
        request = self.factory.get('/proctoring/review/students/', {'department': 'Computer Science'})
        force_authenticate(request, user=self.admin)

        response = ReviewStudentsView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['id'], self.student.id)
        self.assertEqual(response.data[0]['full_name'], 'Student User')

    def test_selected_student_returns_image_list(self):
        request = self.factory.get('/proctoring/review/students/', {
            'department': 'Computer Science',
            'student_id': self.student.id,
        })
        force_authenticate(request, user=self.admin)

        response = ReviewStudentsView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_non_admin_cannot_browse_student_proctoring_data(self):
        request = self.factory.get('/proctoring/review/students/')
        force_authenticate(request, user=self.student_user)

        response = ReviewStudentsView.as_view()(request)

        self.assertEqual(response.status_code, 403)


class ProctorCaptureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='capture-student@example.test',
            password='test-password',
            full_name='Capture Student',
            role='STUDENT',
        )
        self.student = StudentProfile.objects.create(
            user=self.user,
            department='Computer Science',
        )
        department = Department.objects.create(
            name='Capture Department',
            code='CAP',
        )
        course = Course.objects.create(
            course_code='CAP101',
            title='Capture Course',
            department=department,
        )
        exam = Exam.objects.create(
            course=course,
            title='Capture Exam',
            start_time=timezone.now() - timezone.timedelta(minutes=1),
            end_time=timezone.now() + timezone.timedelta(hours=1),
        )
        self.attempt = ExamAttempt.objects.create(
            student=self.student,
            exam=exam,
            status='SUBMITTED',
            score=8,
            total_marks=10,
        )
        self.factory = APIRequestFactory()

    @patch('proctoring.views.send_notification')
    def test_phone_and_multiple_face_captures_are_tagged_without_hiding_results(self, _send_notification):
        with tempfile.TemporaryDirectory() as media_root:
            from django.test import override_settings

            with override_settings(MEDIA_ROOT=media_root):
                for _ in range(2):
                    request = self.factory.post(
                        '/api/proctoring/sessions/capture/',
                        {
                            'exam_id': self.attempt.id,
                            'image_data': 'data:image/jpeg;base64,aGVsbG8=',
                            'metadata': {
                                'face_detected': True,
                                'multiple_faces': True,
                                'mobile_detected': True,
                                'is_warning': True,
                                'warning_reason': 'PHONE_DETECTED',
                            },
                        },
                        format='json',
                    )
                    force_authenticate(request, user=self.user)
                    response = ProctorCaptureView.as_view()(request)

                    self.assertEqual(response.status_code, 201)

        image = ProctorImage.objects.filter(attempt=self.attempt).first()
        self.assertIsNotNone(image)
        self.assertTrue(image.is_suspicious)
        self.assertTrue(image.multiple_faces)
        self.assertTrue(image.mobile_detected)
        self.assertEqual(
            ProctorLog.objects.filter(attempt=self.attempt, event_type='PHONE_DETECTED').count(),
            2,
        )
        self.assertEqual(self.attempt.__class__.objects.get(pk=self.attempt.pk).status, 'SUBMITTED')
