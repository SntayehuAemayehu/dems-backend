import json
import re
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from accounts.models import Department, StudentProfile, TeacherProfile, User
from courses.models import Course, Enrollment
from exams.models import Exam, ExamAttempt, ExaminerAssignment, Question
from exams.serializers import ExamSerializer
from exams.seb_service import build_seb_config
from exams.views import SEBDownloadView
from exams.consumers import ExamProctorConsumer
from proctoring.models import ProctorImage


class StartExamViewTests(TestCase):
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
            department='Computer Science',
            is_enrolled=True,
        )
        self.department = Department.objects.create(
            name='Computer Science',
            code='CS',
        )
        self.course = Course.objects.create(
            course_code='CS101',
            title='Introduction to Computer Science',
            department=self.department,
        )
        self.exam = Exam.objects.create(
            course=self.course,
            title='Test Exam',
            start_time=timezone.now() - timezone.timedelta(minutes=1),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            is_published=True,
        )
        Enrollment.objects.create(
            student=self.student,
            course=self.course,
            status='ACTIVE',
        )
        Question.objects.create(
            exam=self.exam,
            text='Test question',
        )
        self.client.force_authenticate(user=self.user)

    def test_start_exam_allows_enrolled_course_without_department(self):
        self.course.department = None
        self.course.save(update_fields=['department'])

        response = self.client.post(f'/api/exams/{self.exam.id}/start/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('attempt_id', response.data)

    def test_start_exam_creates_attempt_for_valid_course(self):
        response = self.client.post(f'/api/exams/{self.exam.id}/start/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('attempt_id', response.data)
        self.assertEqual(response.data['questions'][0]['text'], 'Test question')

    def test_student_exam_list_includes_published_enrolled_course_exam(self):
        response = self.client.get('/api/exams/')

        self.assertEqual(response.status_code, 200)
        exams = response.data.get('results', response.data)
        self.assertIn(self.exam.id, [exam['id'] for exam in exams])

    def test_student_exam_list_uses_enrollment_not_department_label(self):
        self.student.department = 'Different Department Label'
        self.student.save(update_fields=['department'])

        response = self.client.get('/api/exams/')

        self.assertEqual(response.status_code, 200)
        exams = response.data.get('results', response.data)
        self.assertIn(self.exam.id, [exam['id'] for exam in exams])

    def test_student_exam_list_includes_completed_course_enrollment(self):
        enrollment = Enrollment.objects.get(student=self.student, course=self.course)
        enrollment.status = 'COMPLETED'
        enrollment.save(update_fields=['status'])

        response = self.client.get('/api/exams/')

        self.assertEqual(response.status_code, 200)
        exams = response.data.get('results', response.data)
        self.assertIn(self.exam.id, [exam['id'] for exam in exams])

    def test_exam_results_include_exam_type_and_course_identity(self):
        self.exam.exam_type = 'QUIZ'
        self.exam.save(update_fields=['exam_type'])
        attempt = ExamAttempt.objects.create(
            student=self.student,
            exam=self.exam,
            status='GRADED',
            score=8,
            total_marks=10,
        )

        response = self.client.get('/api/exams/results/')

        self.assertEqual(response.status_code, 200)
        result = next(row for row in response.data if row['id'] == attempt.id)
        self.assertEqual(result['exam_type'], 'QUIZ')
        self.assertEqual(result['course_id'], self.course.id)
        self.assertEqual(result['course_code'], self.course.course_code)

    def test_student_with_completed_enrollment_can_start_exam(self):
        enrollment = Enrollment.objects.get(student=self.student, course=self.course)
        enrollment.status = 'COMPLETED'
        enrollment.save(update_fields=['status'])

        response = self.client.post(f'/api/exams/{self.exam.id}/start/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('attempt_id', response.data)

    def test_live_monitoring_returns_user_id_for_matching_web_rtc_stream(self):
        ExamAttempt.objects.create(
            student=self.student,
            exam=self.exam,
            status='IN_PROGRESS',
        )
        teacher = User.objects.create_user(
            email='teacher@example.com',
            password='test-password',
            full_name='Test Teacher',
            role='TEACHER',
        )
        self.course.instructor = teacher
        self.course.save(update_fields=['instructor'])
        self.client.force_authenticate(user=teacher)

        response = self.client.get(f'/api/exams/{self.exam.id}/live-monitoring/')

        self.assertEqual(response.status_code, 200)
        student = response.data['students'][0]
        self.assertEqual(student['user_id'], self.user.id)

    def test_course_instructor_can_update_exam_and_question_during_live_exam(self):
        teacher = User.objects.create_user(
            email='teacher@example.com',
            password='test-password',
            full_name='Test Teacher',
            role='TEACHER',
        )
        self.course.instructor = teacher
        self.course.save(update_fields=['instructor'])
        self.exam.created_by = teacher
        self.exam.save(update_fields=['created_by'])
        question = self.exam.questions.first()
        self.client.force_authenticate(user=teacher)

        exam_response = self.client.patch(
            f'/api/exams/{self.exam.id}/',
            {'title': 'Updated live exam'},
            format='json',
        )
        question_response = self.client.patch(
            f'/api/exams/questions/{question.id}/',
            {'text': 'Updated live question', 'type': 'SHORT'},
            format='json',
        )

        self.assertEqual(exam_response.status_code, 200)
        self.assertEqual(question_response.status_code, 200)
        self.exam.refresh_from_db()
        question.refresh_from_db()
        self.assertEqual(self.exam.title, 'Updated live exam')
        self.assertEqual(question.text, 'Updated live question')

    def test_teacher_can_filter_proctor_images_by_exam_type(self):
        quiz = Exam.objects.create(
            course=self.course,
            title='Quiz',
            exam_type='QUIZ',
            start_time=timezone.now() - timezone.timedelta(hours=2),
            end_time=timezone.now() - timezone.timedelta(hours=1),
        )
        final = Exam.objects.create(
            course=self.course,
            title='Final',
            exam_type='FINAL',
            start_time=timezone.now() - timezone.timedelta(hours=2),
            end_time=timezone.now() - timezone.timedelta(hours=1),
        )
        quiz_attempt = ExamAttempt.objects.create(
            student=self.student,
            exam=quiz,
            status='SUBMITTED',
        )
        final_attempt = ExamAttempt.objects.create(
            student=self.student,
            exam=final,
            status='SUBMITTED',
        )
        ProctorImage.objects.create(attempt=quiz_attempt, image='proctor_images/quiz.jpg')
        ProctorImage.objects.create(attempt=final_attempt, image='proctor_images/final.jpg')
        teacher = User.objects.create_user(
            email='teacher@example.com',
            password='test-password',
            full_name='Test Teacher',
            role='TEACHER',
        )
        self.course.instructor = teacher
        self.course.save(update_fields=['instructor'])
        self.client.force_authenticate(user=teacher)

        quiz_response = self.client.get(
            f'/api/exams/course/{self.course.id}/proctoring-images/?exam_type=QUIZ&student_id={self.student.id}'
        )
        final_response = self.client.get(
            f'/api/exams/course/{self.course.id}/proctoring-images/?exam_type=FINAL&student_id={self.student.id}'
        )

        self.assertEqual(quiz_response.status_code, 200)
        self.assertEqual(quiz_response.data['total_images'], 1)
        self.assertEqual(quiz_response.data['exam_type'], 'QUIZ')
        self.assertEqual(quiz_response.data['images'][0]['exam_title'], 'Quiz')
        self.assertEqual(final_response.data['exam_type'], 'FINAL')
        self.assertEqual(final_response.status_code, 200)
        self.assertEqual(final_response.data['total_images'], 1)
        self.assertEqual(final_response.data['images'][0]['exam_title'], 'Final')


class ExaminerAssignmentViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.department = Department.objects.create(name='Mathematics', code='MATH')
        self.instructor = User.objects.create_user(
            email='instructor@example.com',
            password='test-password',
            full_name='Course Instructor',
            role='TEACHER',
        )
        self.examiner = User.objects.create_user(
            email='examiner@example.com',
            password='test-password',
            full_name='Department Examiner',
            role='TEACHER',
        )
        TeacherProfile.objects.create(user=self.examiner, department=self.department.name)
        self.other_examiner = User.objects.create_user(
            email='other@example.com',
            password='test-password',
            full_name='Other Department Teacher',
            role='TEACHER',
        )
        TeacherProfile.objects.create(user=self.other_examiner, department='Physics')
        self.course = Course.objects.create(
            course_code='MATH101',
            title='Mathematics',
            department=self.department,
            instructor=self.instructor,
        )
        self.exam = Exam.objects.create(
            course=self.course,
            title='Midterm',
            created_by=self.instructor,
            start_time=timezone.now() - timezone.timedelta(minutes=1),
            end_time=timezone.now() + timezone.timedelta(hours=1),
        )
        self.students = []
        self.attempts = []
        for index in range(2):
            user = User.objects.create_user(
                email=f'student{index}@example.com',
                password='test-password',
                full_name=f'Student {index}',
                role='STUDENT',
            )
            profile = StudentProfile.objects.create(user=user, department=self.department.name)
            self.students.append(user)
            self.attempts.append(ExamAttempt.objects.create(
                student=profile,
                exam=self.exam,
                status='IN_PROGRESS',
            ))

    def test_instructor_assigns_only_selected_active_students_to_department_teacher(self):
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            f'/api/exams/{self.exam.id}/examiner-assignments/',
            {'examiner_id': str(self.examiner.id), 'attempt_ids': [self.attempts[0].id]},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['assigned_count'], 1)
        self.assertTrue(ExaminerAssignment.objects.filter(
            exam=self.exam,
            attempt=self.attempts[0],
            examiner=self.examiner,
        ).exists())
        self.assertFalse(ExaminerAssignment.objects.filter(attempt=self.attempts[1]).exists())

        self.client.force_authenticate(user=self.examiner)
        monitoring = self.client.get(f'/api/exams/{self.exam.id}/live-monitoring/')
        self.assertEqual(monitoring.status_code, 200)
        self.assertEqual([row['attempt_id'] for row in monitoring.data['students']], [self.attempts[0].id])
        self.assertEqual(
            monitoring.data['students'][0]['assigned_examiner_name'],
            self.examiner.full_name,
        )
        exam_list = self.client.get('/api/exams/')
        exam_ids = [row['id'] for row in exam_list.data.get('results', exam_list.data)]
        self.assertIn(self.exam.id, exam_ids)

        question = Question.objects.create(exam=self.exam, text='Original question')
        exam_update = self.client.patch(
            f'/api/exams/{self.exam.id}/',
            {'title': 'Changed title'},
            format='json',
        )
        question_update = self.client.patch(
            f'/api/exams/questions/{question.id}/',
            {'text': 'Changed question'},
            format='json',
        )
        self.assertEqual(exam_update.status_code, 403)
        self.assertEqual(question_update.status_code, 403)

    def test_instructor_cannot_assign_teacher_from_another_department(self):
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            f'/api/exams/{self.exam.id}/examiner-assignments/',
            {'examiner_id': self.other_examiner.id, 'attempt_ids': [self.attempts[0].id]},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ExaminerAssignment.objects.exists())

    def test_unassigned_teacher_cannot_monitor_exam(self):
        self.client.force_authenticate(user=self.other_examiner)

        response = self.client.get(f'/api/exams/{self.exam.id}/live-monitoring/')

        self.assertEqual(response.status_code, 403)


class ExamProctorConsumerJoinTests(IsolatedAsyncioTestCase):
    async def test_authorized_teacher_join_is_forwarded_to_active_student(self):
        consumer = ExamProctorConsumer()
        consumer.user = SimpleNamespace(id=12, role='STUDENT')
        consumer.send = AsyncMock()
        consumer.can_signal_to_staff = AsyncMock(return_value=True)

        await consumer.user_join({
            'user': 'Exam teacher',
            'role': 'TEACHER',
            'user_id': 34,
        })

        consumer.can_signal_to_staff.assert_awaited_once_with(34)
        payload = json.loads(consumer.send.await_args.kwargs['text_data'])
        self.assertEqual(payload['type'], 'user_join')
        self.assertEqual(payload['role'], 'TEACHER')
        self.assertEqual(payload['user_id'], 34)

    async def test_unassigned_teacher_join_is_not_forwarded_to_student(self):
        consumer = ExamProctorConsumer()
        consumer.user = SimpleNamespace(id=12, role='STUDENT')
        consumer.send = AsyncMock()
        consumer.can_signal_to_staff = AsyncMock(return_value=False)

        await consumer.user_join({
            'user': 'Other teacher',
            'role': 'TEACHER',
            'user_id': 34,
        })

        consumer.send.assert_not_awaited()

    async def test_authorized_teacher_can_request_student_stream_refresh(self):
        consumer = ExamProctorConsumer()
        consumer.user = SimpleNamespace(id=12, role='STUDENT')
        consumer.send = AsyncMock()
        consumer.has_active_attempt = AsyncMock(return_value=True)
        consumer.can_signal_to_staff = AsyncMock(return_value=True)

        await consumer.request_student_streams({'requester_id': 34})

        consumer.can_signal_to_staff.assert_awaited_once_with(34)
        payload = json.loads(consumer.send.await_args.kwargs['text_data'])
        self.assertEqual(payload, {'type': 'stream_request', 'sender_id': 34})

    async def test_stream_refresh_is_not_sent_without_active_attempt(self):
        consumer = ExamProctorConsumer()
        consumer.user = SimpleNamespace(id=12, role='STUDENT')
        consumer.send = AsyncMock()
        consumer.has_active_attempt = AsyncMock(return_value=False)
        consumer.can_signal_to_staff = AsyncMock(return_value=True)

        await consumer.request_student_streams({'requester_id': 34})

        consumer.send.assert_not_awaited()


class StartExamProctorImageTests(TestCase):
    def setUp(self):
        StartExamViewTests.setUp(self)

    def test_teacher_can_list_students_and_filter_images_by_student(self):
        quiz = Exam.objects.create(
            course=self.course,
            title='Quiz',
            exam_type='QUIZ',
            start_time=timezone.now() - timezone.timedelta(hours=2),
            end_time=timezone.now() - timezone.timedelta(hours=1),
        )
        first_attempt = ExamAttempt.objects.create(
            student=self.student,
            exam=quiz,
            status='SUBMITTED',
        )
        second_user = User.objects.create_user(
            email='second-student@example.com',
            password='test-password',
            full_name='Second Student',
            role='STUDENT',
        )
        second_student = StudentProfile.objects.create(
            user=second_user,
            department='Computer Science',
            is_enrolled=True,
        )
        second_attempt = ExamAttempt.objects.create(
            student=second_student,
            exam=quiz,
            status='SUBMITTED',
        )
        ProctorImage.objects.create(attempt=first_attempt, image='proctor_images/first.jpg')
        ProctorImage.objects.create(attempt=second_attempt, image='proctor_images/second.jpg')
        teacher = User.objects.create_user(
            email='teacher@example.com',
            password='test-password',
            full_name='Test Teacher',
            role='TEACHER',
        )
        self.course.instructor = teacher
        self.course.save(update_fields=['instructor'])
        self.client.force_authenticate(user=teacher)

        students_response = self.client.get(
            f'/api/exams/course/{self.course.id}/proctoring-images/?exam_type=QUIZ'
        )
        selected_student_response = self.client.get(
            f'/api/exams/course/{self.course.id}/proctoring-images/?exam_type=QUIZ&student_id={second_student.id}'
        )

        self.assertEqual(students_response.status_code, 200)
        self.assertEqual(
            {student['name'] for student in students_response.data['students']},
            {'Test Student', 'Second Student'},
        )
        self.assertEqual(students_response.data['total_images'], 2)
        self.assertEqual(selected_student_response.status_code, 200)
        self.assertEqual(selected_student_response.data['total_images'], 1)
        self.assertEqual(
            selected_student_response.data['images'][0]['student_name'],
            'Second Student',
        )

    def test_student_cannot_view_teacher_proctoring_image_collection(self):
        response = self.client.get(
            f'/api/exams/course/{self.course.id}/proctoring-images/?exam_type=QUIZ'
        )

        self.assertEqual(response.status_code, 403)

    def test_student_can_start_enrolled_exam_when_department_label_differs(self):
        self.student.department = 'Different Department Label'
        self.student.save(update_fields=['department'])

        response = self.client.post(f'/api/exams/{self.exam.id}/start/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('attempt_id', response.data)

    def test_student_with_active_enrollment_can_load_and_start_exam(self):
        self.student.is_enrolled = False
        self.student.save(update_fields=['is_enrolled'])

        list_response = self.client.get('/api/exams/')
        self.assertEqual(list_response.status_code, 200)
        exams = list_response.data.get('results', list_response.data)
        self.assertIn(self.exam.id, [exam['id'] for exam in exams])

        start_response = self.client.post(f'/api/exams/{self.exam.id}/start/')
        self.assertEqual(start_response.status_code, 200)


class SEBConfigTests(SimpleTestCase):
    @override_settings(
        SEB_BASE_URL='https://dems-backend-0dxk.onrender.com',
        FRONTEND_URL='https://dems-frontend.onrender.com',
    )
    def test_url_filter_rules_are_valid_and_allow_application_hosts(self):
        config = build_seb_config(SimpleNamespace(id=42))
        rules = config['URLFilterRules']

        for rule in rules:
            re.compile(rule['expression'])

        self.assertEqual(len(rules), 2)
        self.assertTrue(all(rule['action'] == 1 for rule in rules))
        self.assertRegex(
            'https://dems-backend-0dxk.onrender.com/api/exams/42/seb-entry/',
            rules[0]['expression'],
        )
        self.assertRegex(
            'https://dems-frontend.onrender.com/exams/42/start',
            rules[1]['expression'],
        )

    @override_settings(
        SEB_BASE_URL='',
        BACKEND_URL='https://dems-backend-0dxk.onrender.com',
        FRONTEND_URL='https://dems-frontend.onrender.com',
    )
    def test_config_uses_backend_url_when_seb_base_url_is_not_set(self):
        config = build_seb_config(SimpleNamespace(id=42))

        self.assertEqual(
            config['startURL'],
            'https://dems-backend-0dxk.onrender.com/api/exams/42/seb-entry/',
        )

    def test_existing_exam_launch_url_uses_config_endpoint(self):
        request = APIRequestFactory().get('/api/exams/42/')
        exam = SimpleNamespace(
            id=42,
            is_published=True,
        )

        with override_settings(SEB_ENABLED=True):
            serializer = ExamSerializer(context={'request': request})
            url = serializer.get_seb_file_url(exam)

        self.assertEqual(url, 'http://testserver/api/exams/42/seb-config/')

    @override_settings(SEB_ENABLED=True)
    def test_seb_download_generates_current_config_and_enables_legacy_exam(self):
        exam = SimpleNamespace(
            id=42,
            seb_config_file=SimpleNamespace(name='old-config.seb'),
            end_time=timezone.now() + timezone.timedelta(minutes=1),
            seb_config_key='old-key',
            seb_generated_at=None,
            seb_enabled=False,
            save=Mock(),
        )
        request = APIRequestFactory().get('/api/exams/42/seb-config/')

        with (
            patch('exams.views.Exam.objects.get', return_value=exam),
            patch('exams.views.generate_seb_file', return_value=('new-key', b'fresh-config')),
        ):
            response = SEBDownloadView.as_view()(request, exam_id=42)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'fresh-config')
        self.assertEqual(exam.seb_config_key, 'new-key')
        self.assertTrue(exam.seb_enabled)
        exam.save.assert_called_once_with(
            update_fields=['seb_config_key', 'seb_generated_at', 'seb_enabled']
        )
