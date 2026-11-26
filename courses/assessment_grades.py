from decimal import Decimal


ASSESSMENT_CATEGORIES = ('quiz', 'mid', 'final', 'assignment')


def build_assessment_grade_breakdowns(course_student_pairs):
    pairs = set(course_student_pairs)
    breakdowns = {
        pair: {
            category: {'obtained': Decimal('0'), 'possible': Decimal('0')}
            for category in ASSESSMENT_CATEGORIES
        }
        for pair in pairs
    }
    if not pairs:
        return breakdowns

    course_ids = {course_id for course_id, _ in pairs}
    student_ids = {student_id for _, student_id in pairs}

    from courses.models import AssignmentSubmission
    from exams.models import ExamAttempt

    exam_categories = {
        'QUIZ': 'quiz',
        'MID': 'mid',
        'MIDTERM': 'mid',
        'FINAL': 'final',
    }
    attempts = ExamAttempt.objects.filter(
        exam__course_id__in=course_ids,
        student_id__in=student_ids,
        status__in=('SUBMITTED', 'GRADED'),
        score__isnull=False,
    ).select_related('exam')
    for attempt in attempts:
        key = (attempt.exam.course_id, attempt.student_id)
        category = exam_categories.get(attempt.exam.exam_type)
        if key in breakdowns and category:
            breakdowns[key][category]['obtained'] += Decimal(str(attempt.score))
            breakdowns[key][category]['possible'] += Decimal(
                str(attempt.total_marks or attempt.exam.total_marks or 0)
            )

    submissions = AssignmentSubmission.objects.filter(
        assignment__course_id__in=course_ids,
        student_id__in=student_ids,
        marks_obtained__isnull=False,
    ).select_related('assignment')
    for submission in submissions:
        key = (submission.assignment.course_id, submission.student_id)
        if key in breakdowns:
            breakdowns[key]['assignment']['obtained'] += Decimal(
                str(submission.marks_obtained)
            )
            breakdowns[key]['assignment']['possible'] += Decimal(
                str(submission.assignment.total_marks or 0)
            )

    return breakdowns
