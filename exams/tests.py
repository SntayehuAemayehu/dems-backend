from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Department, StudentProfile, User
from courses.models import Course, Enrollment
from exams.models import Exam, ExamAttempt, Question
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
