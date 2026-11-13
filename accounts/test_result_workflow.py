from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Department, StudentProfile, User
from courses.models import Course, Enrollment


class DepartmentResultWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.head = User.objects.create_user(
            email='head@example.com',
            password='test-password',
            full_name='Department Head',
            role='DEPT_HEAD',
        )
        self.registrar = User.objects.create_user(
            email='registrar@example.com',
            password='test-password',
            full_name='Registrar',
            role='REGISTRAR',
        )
        student_user = User.objects.create_user(
            email='student@example.com',
            password='test-password',
            full_name='Student',
            role='STUDENT',
        )
        self.student = StudentProfile.objects.create(user=student_user, year=2)
        department = Department.objects.create(
            name='Computer Science',
            code='CS',
            head=self.head,
        )
        course = Course.objects.create(
            course_code='CS201',
            title='Algorithms',
            department=department,
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=course,
            status='COMPLETED',
            grade_letter='B',
            percentage_score=82,
            total_marks_obtained=82,
            total_marks_possible=100,
            result_submitted_to_department=True,
        )

    def test_head_can_view_submitted_grade_and_forward_it_without_editing(self):
        self.client.force_authenticate(self.head)
        visible = self.client.get('/api/auth/dept-head/results/')
        self.assertEqual(visible.status_code, 200)
        self.assertEqual(visible.data['results'][0]['year'], 2)
        self.assertEqual(visible.data['results'][0]['grade'], 'B')
        self.assertEqual(
            self.client.post('/api/auth/dept-head/results/', {}, format='json').status_code,
            405,
        )

        with patch('accounts.views.send_notification'):
            forwarded = self.client.post(
                '/api/auth/dept-head/send-results/',
                {'student_id': self.student.id},
                format='json',
            )

        self.assertEqual(forwarded.status_code, 200)
        self.enrollment.refresh_from_db()
        self.assertTrue(self.enrollment.result_sent_to_registrar)

        self.client.force_authenticate(self.registrar)
        registrar_results = self.client.get('/api/auth/registrar/sent-results/')
        self.assertEqual(registrar_results.status_code, 200)
        self.assertEqual(registrar_results.data['results'][0]['student_id'], self.student.id)
        self.assertEqual(
            self.client.post('/api/auth/registrar/sent-results/', {}, format='json').status_code,
            405,
        )

    def test_head_can_forward_selected_students_in_bulk(self):
        self.client.force_authenticate(self.head)

        with patch('accounts.views.send_notification'):
            response = self.client.post(
                '/api/auth/dept-head/send-results/',
                {'student_ids': [self.student.id]},
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['sent_student_ids'], [self.student.id])
        self.enrollment.refresh_from_db()
        self.assertTrue(self.enrollment.result_sent_to_registrar)
