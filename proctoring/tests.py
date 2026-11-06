from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import StudentProfile, User
from proctoring.views import ReviewStudentsView


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
