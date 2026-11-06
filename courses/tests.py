from unittest.mock import Mock, patch

import requests
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Department, StudentProfile, User
from courses.models import (
    Assignment,
    AssignmentSubmission,
    Course,
    CourseAIConversation,
    CourseMaterial,
    Enrollment,
)
from exams.models import Exam, ExamAttempt


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


class TeacherCourseGradesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.department = Department.objects.create(name='Mathematics', code='MATH')
        self.teacher = User.objects.create_user(
            email='teacher-grades@example.com',
            password='test-password',
            full_name='Course Teacher',
            role='TEACHER',
        )
        self.student_user = User.objects.create_user(
            email='student-grades@example.com',
            password='test-password',
            full_name='Grade Student',
            role='STUDENT',
        )
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            department=self.department.name,
        )
        self.course = Course.objects.create(
            course_code='MATH101',
            title='Mathematics',
            department=self.department,
            instructor=self.teacher,
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            status='ACTIVE',
        )
        self.client.force_authenticate(user=self.teacher)

    def test_course_grades_include_marks_by_assessment_category(self):
        for exam_type, score in (('QUIZ', 8), ('MID', 70), ('FINAL', 85)):
            exam = Exam.objects.create(
                course=self.course,
                title=f'{exam_type} exam',
                exam_type=exam_type,
                created_by=self.teacher,
                start_time=timezone.now() - timezone.timedelta(hours=2),
                end_time=timezone.now() - timezone.timedelta(hours=1),
                total_marks=100,
            )
            ExamAttempt.objects.create(
                student=self.student,
                exam=exam,
                status='SUBMITTED' if exam_type == 'QUIZ' else 'GRADED',
                score=score,
                total_marks=100,
            )

        assignment = Assignment.objects.create(
            course=self.course,
            title='Assignment',
            due_date=timezone.now() - timezone.timedelta(days=1),
            total_marks=20,
        )
        AssignmentSubmission.objects.create(
            assignment=assignment,
            student=self.student,
            marks_obtained=18,
        )

        response = self.client.get(
            f'/api/courses/teacher/course/{self.course.id}/grades/'
        )

        self.assertEqual(response.status_code, 200)
        student_grade = response.data['students'][0]
        self.assertEqual(student_grade['assessment_grades'], {
            'quiz': {'obtained': 8.0, 'possible': 100.0},
            'mid': {'obtained': 70.0, 'possible': 100.0},
            'assignment': {'obtained': 18.0, 'possible': 20.0},
            'final': {'obtained': 85.0, 'possible': 100.0},
        })
        self.assertEqual(student_grade['total_marks_obtained'], 181.0)
        self.assertEqual(student_grade['total_marks_possible'], 320.0)
        self.assertEqual(student_grade['percentage'], 56.56)
        self.assertEqual(student_grade['grade_letter'], 'C')

    @override_settings(GEMINI_API_KEY='test-gemini-key')
    @patch('courses.views.requests.post')
    def test_course_ai_chat_returns_gemini_answer_for_course_instructor(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            'candidates': [{'content': {'parts': [{'text': 'A course answer'}]}}],
        }
        post.return_value = response

        result = self.client.post(
            f'/api/courses/{self.course.id}/ai-chat/',
            {'messages': [{'role': 'user', 'content': 'Explain this course'}]},
            format='json',
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['answer'], 'A course answer')
        self.assertIn('conversation', result.data)
        self.assertEqual(result.data['conversation']['title'], 'Explain this course')
        self.assertEqual(post.call_args.kwargs['headers']['x-goog-api-key'], 'test-gemini-key')

        conversations = self.client.get(f'/api/courses/{self.course.id}/ai-chat/')
        self.assertEqual(conversations.status_code, 200)
        self.assertEqual(len(conversations.data), 1)
        self.assertEqual(
            conversations.data[0]['id'],
            result.data['conversation']['id'],
        )

        conversation = self.client.get(
            f'/api/courses/{self.course.id}/ai-chat/',
            {'conversation_id': result.data['conversation']['id']},
        )
        self.assertEqual(conversation.status_code, 200)
        self.assertEqual(len(conversation.data['messages']), 2)

    @override_settings(GEMINI_API_KEY='test-gemini-key')
    @patch('courses.views.requests.post')
    def test_course_ai_chat_continues_saved_conversation(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            'candidates': [{'content': {'parts': [{'text': 'A course answer'}]}}],
        }
        post.return_value = response
        conversation = CourseAIConversation.objects.create(
            user=self.teacher,
            course=self.course,
            title='First question',
            messages=[
                {'role': 'user', 'content': 'First question'},
                {'role': 'assistant', 'content': 'First answer'},
            ],
        )

        result = self.client.post(
            f'/api/courses/{self.course.id}/ai-chat/',
            {
                'conversation_id': conversation.id,
                'message': 'My follow-up question',
            },
            format='json',
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['conversation']['id'], conversation.id)
        conversation.refresh_from_db()
        self.assertEqual(len(conversation.messages), 4)
        self.assertEqual(
            post.call_args.kwargs['json']['contents'][-1]['parts'][0]['text'],
            'My follow-up question',
        )

        other_user_conversation = CourseAIConversation.objects.create(
            user=self.student_user,
            course=self.course,
            title='Private conversation',
        )
        private_result = self.client.get(
            f'/api/courses/{self.course.id}/ai-chat/',
            {'conversation_id': other_user_conversation.id},
        )
        self.assertEqual(private_result.status_code, 404)

    @override_settings(GEMINI_API_KEY='test-gemini-key')
    @patch('courses.views.requests.post')
    def test_course_ai_chat_reports_gemini_access_error(self, post):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError(
            response=Mock(status_code=403),
        )
        post.return_value = response

        result = self.client.post(
            f'/api/courses/{self.course.id}/ai-chat/',
            {'messages': [{'role': 'user', 'content': 'Explain this course'}]},
            format='json',
        )

        self.assertEqual(result.status_code, 503)
        self.assertIn('GEMINI_API_KEY', result.data['error'])

    @override_settings(GEMINI_API_KEY='test-gemini-key')
    @patch('courses.views.requests.post')
    def test_course_ai_chat_reports_gemini_quota_error(self, post):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError(
            response=Mock(status_code=429),
        )
        post.return_value = response

        result = self.client.post(
            f'/api/courses/{self.course.id}/ai-chat/',
            {'messages': [{'role': 'user', 'content': 'Explain this course'}]},
            format='json',
        )

        self.assertEqual(result.status_code, 503)
        self.assertIn('usage limit', result.data['error'])

    @override_settings(GEMINI_API_KEY='test-gemini-key')
    @patch('courses.views.requests.post')
    def test_course_ai_chat_includes_gemini_bad_request_reason(self, post):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError(
            response=Mock(
                status_code=400,
                json=Mock(return_value={
                    'error': {'message': 'API key not valid. Please pass a valid API key.'},
                }),
            ),
        )
        post.return_value = response

        result = self.client.post(
            f'/api/courses/{self.course.id}/ai-chat/',
            {'messages': [{'role': 'user', 'content': 'Explain this course'}]},
            format='json',
        )

        self.assertEqual(result.status_code, 502)
        self.assertIn('API key not valid', result.data['error'])

    @override_settings(GEMINI_API_KEY='')
    def test_course_ai_chat_reports_missing_gemini_configuration(self):
        result = self.client.post(
            f'/api/courses/{self.course.id}/ai-chat/',
            {'messages': [{'role': 'user', 'content': 'Explain this course'}]},
            format='json',
        )

        self.assertEqual(result.status_code, 503)
        self.assertIn('GEMINI_API_KEY', result.data['error'])
