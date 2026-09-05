from django.contrib import admin
from .models import Exam, Question, ExamAttempt, Answer

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'duration_minutes', 'start_time', 'end_time', 'is_published')
    list_filter = ('is_published', 'course', 'start_time')
    search_fields = ('title', 'description', 'course__title', 'course__course_code')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Basic Information', {'fields': ('title', 'description', 'course')}),
        ('Timing', {'fields': ('duration_minutes', 'start_time', 'end_time')}),
        ('Marks', {'fields': ('total_marks', 'passing_mark')}),
        ('Settings', {'fields': ('is_published', 'proctoring_enabled')}),
        ('Metadata', {'fields': ('created_by', 'created_at')}),
    )

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text_preview', 'exam', 'type', 'marks', 'order')
    list_filter = ('type', 'exam')
    search_fields = ('text', 'exam__title')
    
    def text_preview(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Question'

@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam', 'status', 'score', 'percentage', 'passed')
    list_filter = ('status', 'passed', 'exam')
    search_fields = ('student__user__full_name', 'exam__title')
    readonly_fields = ('start_time',)

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'marks_obtained', 'is_correct')
    list_filter = ('is_correct',)
    search_fields = ('attempt__student__user__full_name', 'question__text')