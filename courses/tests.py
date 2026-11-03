from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Department, StudentProfile, User
from courses.models import Assignment, AssignmentSubmission, Course, CourseMaterial, Enrollment


class StudentCourseContentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='student@example.com',
            password='test-password',
            full_name='Test Student',
            role='STUDENT',
        )
        self.student = StudentProfile.objects.create(
            user=self.user,
            department='A department label that does not match',
            is_enrolled=False,
        )
        self.department = Department.objects.create(
            name='Computer Science',
            code='CS',
        )
        self.course = Course.objects.create(
            course_code='CS101',
            title='Introduction to Computer Science',
            department=self.department,
            is_approved=False,
        )
        Enrollment.objects.create(
            student=self.student,
            course=self.course,
            status='ACTIVE',
        )
        self.material = CourseMaterial.objects.create(
            course=self.course,
            title='Lecture file',
        )
        self.assignment = Assignment.objects.create(
            course=self.course,
            title='First assignment',
            due_date=timezone.now() + timezone.timedelta(days=1),
        )
        self.client.force_authenticate(user=self.user)

    def test_active_enrollment_makes_course_visible(self):
        response = self.client.get('/api/courses/')

        self.assertEqual(response.status_code, 200)
        courses = response.data.get('results', response.data)
        self.assertIn(self.course.id, [course['id'] for course in courses])

    def test_active_enrollment_allows_course_detail(self):
        response = self.client.get(f'/api/courses/{self.course.id}/')

        self.assertEqual(response.status_code, 200)

    def test_active_enrollment_loads_course_materials_and_assignments(self):
        materials_response = self.client.get(
            f'/api/courses/student/{self.course.id}/materials/'
        )
        assignments_response = self.client.get(
            f'/api/courses/student/{self.course.id}/assignments/'
        )

        self.assertEqual(materials_response.status_code, 200)
        materials = materials_response.data.get('results', materials_response.data)
        self.assertIn(self.material.id, [material['id'] for material in materials])

        self.assertEqual(assignments_response.status_code, 200)
        self.assertIn(
            self.assignment.id,
            [assignment['id'] for assignment in assignments_response.data],
        )

    def test_completed_enrollment_keeps_course_content_available(self):
        enrollment = Enrollment.objects.get(student=self.student, course=self.course)
        enrollment.status = 'COMPLETED'
        enrollment.save(update_fields=['status'])

        courses_response = self.client.get('/api/courses/')
        course_data = courses_response.data.get('results', courses_response.data)
        self.assertIn(self.course.id, [course['id'] for course in course_data])
        self.assertTrue(
            next(course for course in course_data if course['id'] == self.course.id)['is_enrolled']
        )

        materials_response = self.client.get(
            f'/api/courses/student/{self.course.id}/materials/'
        )
        general_materials_response = self.client.get(
            f'/api/courses/{self.course.id}/materials/'
        )
        assignments_response = self.client.get(
            f'/api/courses/student/{self.course.id}/assignments/'
        )

        self.assertEqual(materials_response.status_code, 200)
        materials = materials_response.data.get('results', materials_response.data)
        self.assertIn(self.material.id, [material['id'] for material in materials])
        self.assertEqual(general_materials_response.status_code, 200)
        general_materials = general_materials_response.data.get(
            'results',
            general_materials_response.data,
        )
        self.assertIn(self.material.id, [material['id'] for material in general_materials])
        self.assertEqual(assignments_response.status_code, 200)
        self.assertIn(
            self.assignment.id,
            [assignment['id'] for assignment in assignments_response.data],
        )

    def test_enrollment_request_activates_existing_pending_enrollment(self):
        self.student.department = self.department.name
        self.student.is_enrolled = True
        self.student.payment_status = 'VERIFIED'
        self.student.save(update_fields=['department', 'is_enrolled', 'payment_status'])
        self.course.is_approved = True
        self.course.save(update_fields=['is_approved'])
        enrollment = Enrollment.objects.get(student=self.student, course=self.course)
        enrollment.status = 'PENDING'
        enrollment.save(update_fields=['status'])

        response = self.client.post(
            '/api/courses/enrollments/',
            {'course': self.course.id},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'ACTIVE')
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, 'ACTIVE')

    def test_enrolling_again_in_completed_course_is_idempotent(self):
        enrollment = Enrollment.objects.get(student=self.student, course=self.course)
        enrollment.status = 'COMPLETED'
        enrollment.save(update_fields=['status'])

        response = self.client.post(
            '/api/courses/enrollments/',
            {'course': self.course.id},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'COMPLETED')
        self.assertEqual(
            Enrollment.objects.filter(student=self.student, course=self.course).count(),
            1,
        )

    def test_assignment_results_include_course_id_for_result_grouping(self):
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
            marks_obtained=8,
        )

        response = self.client.get('/api/courses/student/assignments/results/')

        self.assertEqual(response.status_code, 200)
        result = next(row for row in response.data if row['id'] == submission.id)
        self.assertEqual(result['course_id'], self.course.id)

    def test_my_grades_includes_student_year_and_semester(self):
        self.student.year = 3
        self.student.current_semester = 5
        self.student.save(update_fields=['year', 'current_semester'])

        response = self.client.get('/api/courses/my-grades/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['year'], 3)
        self.assertEqual(response.data['semester'], 5)
