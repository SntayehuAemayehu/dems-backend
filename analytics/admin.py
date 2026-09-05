# analytics/admin.py - COMPLETE FIXED

from django.contrib import admin
from .models import (
    SystemLog, DailyAnalytics, SystemConfig, 
    BankAccount, PaymentPeriod, FeeStructure, 
    StudentPaymentSchedule,   # ✅ ADD THIS
    StudentAccessLog,         # ✅ ADD THIS
    IDSequence,               # ✅ ADD THIS
    StudentServiceAccess      # ✅ ADD THIS
)


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'log_level', 'created_at')
    list_filter = ('log_level', 'created_at')
    search_fields = ('action', 'user__email', 'user__full_name')
    readonly_fields = ('created_at',)


@admin.register(DailyAnalytics)
class DailyAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('date', 'total_students', 'total_courses', 'total_enrollments', 'total_payments')
    list_filter = ('date',)
    search_fields = ('date',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ('key', 'value_preview', 'updated_at')
    search_fields = ('key', 'description')
    
    def value_preview(self, obj):
        return obj.value[:50] + '...' if len(obj.value) > 50 else obj.value
    value_preview.short_description = 'Value'


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('bank_name', 'account_name', 'account_number', 'is_active', 'is_default')
    list_filter = ('is_active', 'is_default')
    search_fields = ('bank_name', 'account_name', 'account_number')


@admin.register(PaymentPeriod)
class PaymentPeriodAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_months', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ('department', 'payment_period', 'amount', 'is_active')
    list_filter = ('is_active', 'department')
    search_fields = ('department__name', 'payment_period__name')


@admin.register(StudentPaymentSchedule)
class StudentPaymentScheduleAdmin(admin.ModelAdmin):
    list_display = ('student', 'fee_structure', 'period_number', 'due_date', 'status', 'total_amount')
    list_filter = ('status', 'fee_structure')
    search_fields = ('student__user__full_name', 'student__student_id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(StudentAccessLog)
class StudentAccessLogAdmin(admin.ModelAdmin):
    list_display = ('student', 'access_type', 'allowed', 'created_at')
    list_filter = ('access_type', 'allowed')
    search_fields = ('student__user__full_name', 'reason')
    readonly_fields = ('created_at',)


@admin.register(IDSequence)
class IDSequenceAdmin(admin.ModelAdmin):
    list_display = ('prefix', 'year', 'last_number', 'updated_at')
    list_filter = ('prefix', 'year')
    search_fields = ('prefix',)


@admin.register(StudentServiceAccess)
class StudentServiceAccessAdmin(admin.ModelAdmin):
    list_display = ('student', 'service_type', 'is_allowed', 'created_at')
    list_filter = ('service_type', 'is_allowed')
    search_fields = ('student__user__full_name',)