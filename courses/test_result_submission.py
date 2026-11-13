from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Department, StudentProfile, User
from courses.models import Course, Enrollment


class TeacherResultSubmissionTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email='teacher@example.com',
            password='test-password',
            full_name='Test Teacher',
            role='TEACHER',
        )
        self.student_user = User.objects.create_user(
            email='student@example.com',
            password='test-password',
            full_name='Test Student',
            role='STUDENT',
        )
        self.student = StudentProfile.objects.create(user=self.student_user)
        department = Department.objects.create(name='Computer Science', code='CS')
        self.course = Course.objects.create(
            course_code='CS101',
            title='Computer Science',
            instructor=self.teacher,
            department=department,
        )
        self.enrollment = Enrollment.objects.create(student=self.student, course=self.course)
        self.client = APIClient()

    @staticmethod
    def set_completed_grade(enrollment):
        enrollment.status = 'COMPLETED'
        enrollment.grade_letter = 'A'
        enrollment.percentage_score = 90
        enrollment.total_marks_obtained = 90
        enrollment.total_marks_possible = 100
        enrollment.save(update_fields=[
            'status',
            'grade_letter',
            'percentage_score',
            'total_marks_obtained',
            'total_marks_possible',
        ])

    def test_assigned_teacher_can_submit_completed_result_to_department(self):
        self.client.force_authenticate(self.teacher)

        with patch.object(
            Enrollment,
            'update_course_grade',
            autospec=True,
            side_effect=self.set_completed_grade,
        ):
            response = self.client.post(
                f'/api/courses/teacher/course/{self.course.id}/send-result/',
                {'student_id': self.student.id},
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.enrollment.refresh_from_db()
        self.assertTrue(self.enrollment.result_submitted_to_department)
        self.assertEqual(self.enrollment.result_submitted_by, self.teacher)

    def test_other_teacher_cannot_submit_result(self):
        other_teacher = User.objects.create_user(
            email='other@example.com',
            password='test-password',
            full_name='Other Teacher',
            role='TEACHER',
        )
        self.client.force_authenticate(other_teacher)

        response = self.client.post(
            f'/api/courses/teacher/course/{self.course.id}/send-result/',
            {'student_id': self.student.id},
            format='json',
        )

        self.assertEqual(response.status_code, 404)
        self.enrollment.refresh_from_db()
        self.assertFalse(self.enrollment.result_submitted_to_department)

    def test_teacher_can_submit_selected_enrollments_in_bulk(self):
        self.client.force_authenticate(self.teacher)

        with patch.object(
            Enrollment,
            'update_course_grade',
            autospec=True,
            side_effect=self.set_completed_grade,
        ):
            response = self.client.post(
                '/api/courses/teacher/results/send/',
                {'enrollment_ids': [self.enrollment.id]},
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['submitted_ids'], [self.enrollment.id])
        self.assertEqual(response.data['skipped_ids'], [])
        self.enrollment.refresh_from_db()
        self.assertTrue(self.enrollment.result_submitted_to_department)
