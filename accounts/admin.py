# accounts/admin.py - COMPLETE FIXED

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, StudentProfile, TeacherProfile, Department, RegistrationConfig, PasswordResetOTP


class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'full_name', 'role', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('email', 'full_name', 'phone')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'phone', 'profile_picture')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'phone', 'password1', 'password2', 'role'),
        }),
    )


class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_id', 'department', 'payment_status', 'is_enrolled', 'cgpa')
    list_filter = ('payment_status', 'department', 'gender', 'is_enrolled')
    search_fields = ('user__email', 'user__full_name', 'student_id')
    readonly_fields = ('enrollment_date', 'documents_verified_at', 'activated_at')


class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee_id', 'department', 'is_verified')
    list_filter = ('department', 'is_verified')
    search_fields = ('user__email', 'user__full_name', 'employee_id')


class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'head', 'established_year')
    search_fields = ('name', 'code')


class RegistrationConfigAdmin(admin.ModelAdmin):
    list_display = ('academic_year', 'semester', 'registration_start_date', 'registration_end_date', 'is_active')
    list_filter = ('is_active', 'semester')
    search_fields = ('academic_year',)


admin.site.register(User, UserAdmin)
admin.site.register(StudentProfile, StudentProfileAdmin)
admin.site.register(TeacherProfile, TeacherProfileAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(RegistrationConfig, RegistrationConfigAdmin)
@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'otp', 'is_used', 'created_at', 'expires_at')
    list_filter = ('is_used',)
    search_fields = ('email', 'otp')
    readonly_fields = ('created_at',)