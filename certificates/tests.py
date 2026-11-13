import tempfile
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Department, StudentProfile, User
from certificates.models import Certificate
from courses.models import Course, Enrollment
from services.certificate_service import certificate_service


class RegistrarCertificateIssueTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        settings_override = override_settings(MEDIA_ROOT=self.media.name)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.addCleanup(self.media.cleanup)

        self.student_user = User.objects.create_user(
            email='student@example.com',
            password='test-password',
            full_name='Test Student',
            role='STUDENT',
        )
        self.student = StudentProfile.objects.create(user=self.student_user)
        self.registrar = User.objects.create_user(
            email='registrar@example.com',
            password='test-password',
            full_name='Test Registrar',
            role='REGISTRAR',
        )
        self.teacher = User.objects.create_user(
            email='teacher@example.com',
            password='test-password',
            full_name='Test Teacher',
            role='TEACHER',
        )
        department = Department.objects.create(name='Computer Science', code='CS')
        course = Course.objects.create(
            course_code='CS101',
            title='Computer Science',
            department=department,
            instructor=self.teacher,
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=course,
            status='COMPLETED',
            grade_letter='A',
            percentage_score=90,
            result_submitted_to_department=True,
            result_sent_to_registrar=True,
        )
        self.client = APIClient()

    def test_certificate_is_hidden_until_issued_by_registrar(self):
        Certificate.objects.create(
            student=self.student,
            enrollment=self.enrollment,
            course=self.enrollment.course,
            certification_id='CERT-HIDDEN-2026',
            is_published=False,
        )
        self.client.force_authenticate(self.student_user)

        response = self.client.get('/api/certificates/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_certificate_grade_uses_marks_and_credit_weighted_grade_scale(self):
        self.enrollment.total_marks_obtained = 72
        self.enrollment.total_marks_possible = 100
        self.enrollment.save(update_fields=['total_marks_obtained', 'total_marks_possible'])
        other_course = Course.objects.create(
            course_code='CS102',
            title='Data Structures',
            department=self.enrollment.course.department,
            year=1,
            semester='2',
        )
        other_enrollment = Enrollment.objects.create(
            student=self.student,
            course=other_course,
            status='ACTIVE',
        )
        Certificate.objects.create(
            student=self.student,
            enrollment=self.enrollment,
            course=self.enrollment.course,
            certification_id='CERT-REAL-GRADE-2026',
            is_published=True,
        )
        self.client.force_authenticate(self.student_user)

        response = self.client.get('/api/certificates/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['grade'], 'B')
        self.assertEqual(response.data[0]['student_id'], self.student.student_id)
        self.assertEqual(response.data[0]['student_name'], 'Test Student')
        self.assertEqual(response.data[0]['year'], 1)
        self.assertEqual(response.data[0]['semester'], 1)
        self.assertEqual(response.data[0]['gpa'], 3.0)
        self.assertEqual(response.data[0]['cgpa'], 3.0)
        self.assertEqual(len(response.data[0]['courses']), 2)

        released_course = next(
            course for course in response.data[0]['courses']
            if course['course_id'] == self.enrollment.course_id
        )
        pending_course = next(
            course for course in response.data[0]['courses']
            if course['course_id'] == other_enrollment.course_id
        )
        self.assertEqual(released_course['score'], 72.0)
        self.assertEqual(released_course['score_possible'], 100.0)
        self.assertEqual(released_course['gpa'], 3.0)
        self.assertIsNone(pending_course['score'])
        self.assertEqual(pending_course['grade'], 'Not issued')

    def test_course_certificate_service_builds_a_pdf(self):
        generated = certificate_service.generate_course_certificate(self.student, self.enrollment)

        self.assertTrue(generated['pdf'].startswith(b'%PDF'))
        self.assertIn('certification_id', generated)

    @patch('certificates.views.certificate_service.generate_course_certificate')
    def test_registrar_issues_certificate_and_it_becomes_visible(self, generate_certificate):
        generate_certificate.return_value = {
            'certification_id': 'CERT-ISSUED-2026',
            'filename': 'test-certificate.pdf',
            'pdf': b'%PDF-1.4 test certificate',
        }
        endpoint = f'/api/certificates/enrollments/{self.enrollment.id}/generate/'
        self.client.force_authenticate(self.teacher)
        forbidden = self.client.post(endpoint, format='json')
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_authenticate(self.registrar)
        issued = self.client.post(endpoint, format='json')
        self.assertEqual(issued.status_code, 201)
        self.assertTrue(Certificate.objects.get(enrollment=self.enrollment).is_published)

        self.client.force_authenticate(self.student_user)
        visible = self.client.get('/api/certificates/')
        self.assertEqual(visible.status_code, 200)
        self.assertEqual(len(visible.data), 1)
        self.assertEqual(visible.data[0]['certification_id'], 'CERT-ISSUED-2026')
        self.assertEqual(visible.data[0]['grade'], 'A+')
        self.assertEqual(visible.data[0]['gpa'], 4.0)
        self.assertEqual(visible.data[0]['cgpa'], 4.0)
        self.assertEqual(visible.data[0]['department'], 'Computer Science')
