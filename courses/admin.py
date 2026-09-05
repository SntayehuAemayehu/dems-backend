from django.contrib import admin
from .models import Course, CourseMaterial, Enrollment

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('course_code', 'title', 'instructor', 'semester', 'credit_hours', 'capacity', 'is_active', 'is_approved')
    list_filter = ('semester', 'is_active', 'is_approved', 'department')
    search_fields = ('course_code', 'title', 'description')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Course Information', {'fields': ('course_code', 'title', 'description', 'credit_hours')}),
        ('Academic Details', {'fields': ('semester', 'academic_year', 'department')}),
        ('Management', {'fields': ('instructor', 'capacity', 'is_active')}),
        ('Approval', {'fields': ('is_approved', 'approved_by')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )

@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'material_type', 'uploaded_by', 'uploaded_at')
    list_filter = ('material_type', 'uploaded_at')
    search_fields = ('title', 'description', 'course__title')

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'status', 'enrollment_date', 'grade')
    list_filter = ('status', 'enrollment_date')
    search_fields = ('student__user__full_name', 'course__course_code', 'course__title')
    readonly_fields = ('enrollment_date',)