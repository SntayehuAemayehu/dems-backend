# analytics/serializers.py - COMPLETE FIXED VERSION
# FIXED: Type error between datetime.date and datetime.datetime

from rest_framework import serializers
from .models import (
    SystemLog, DailyAnalytics, SystemConfig, 
    BankAccount, PaymentPeriod, FeeStructure, StudentPaymentSchedule
)


class SystemLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = SystemLog
        fields = '__all__'
        read_only_fields = ['created_at']
    
    def get_user_name(self, obj):
        return obj.user.full_name if obj.user else None


class DailyAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyAnalytics
        fields = '__all__'


class SystemConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemConfig
        fields = '__all__'


class BankAccountSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = BankAccount
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None


class PaymentPeriodSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    duration_in_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentPeriod
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None
    
    def get_duration_display(self, obj):
        return obj.get_duration_display()
    
    def get_duration_in_minutes(self, obj):
        return obj.get_duration_in_minutes()


class FeeStructureSerializer(serializers.ModelSerializer):
    department_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    payment_period_name = serializers.SerializerMethodField()
    payment_period_duration = serializers.SerializerMethodField()
    
    class Meta:
        model = FeeStructure
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def get_department_name(self, obj):
        return obj.department.name if obj.department else None
    
    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None
    
    def get_payment_period_name(self, obj):
        return obj.payment_period.name if obj.payment_period else None
    
    def get_payment_period_duration(self, obj):
        return obj.payment_period.duration_months if obj.payment_period else 0
    
    # ✅ Override create to handle department ID correctly
    def create(self, validated_data):
        department = validated_data.get('department')
        # If department is an ID, convert to Department object
        if department and isinstance(department, int):
            from accounts.models import Department
            department = Department.objects.get(id=department)
            validated_data['department'] = department
        return super().create(validated_data)


# analytics/serializers.py - UPDATE StudentPaymentScheduleSerializer

class StudentPaymentScheduleSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    fee_structure_details = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()
    minutes_overdue = serializers.SerializerMethodField()
    minutes_remaining = serializers.SerializerMethodField()
    can_take_exam = serializers.SerializerMethodField()
    penalty_breakdown = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    payment_period_display = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()
    can_access = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentPaymentSchedule
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'penalty_amount', 'total_amount']
    
    def get_student_name(self, obj):
        return obj.student.user.full_name if obj.student else None
    
    def get_department_name(self, obj):
        return obj.fee_structure.department.name if obj.fee_structure else None
    
    def get_fee_structure_details(self, obj):
        if obj.fee_structure:
            return {
                'id': obj.fee_structure.id,
                'payment_period': obj.fee_structure.payment_period.name if obj.fee_structure.payment_period else None,
                'penalty_per_day': float(obj.fee_structure.penalty_per_day),
                'grace_period_days': obj.fee_structure.grace_period_days,
                'base_amount': float(obj.fee_structure.amount),
                'is_active': obj.fee_structure.is_active,
            }
        return None
    
    def get_days_overdue(self, obj):
        """Calculate days overdue"""
        from django.utils import timezone
        if obj.status == 'PAID':
            return 0
        now = timezone.now()
        if now <= obj.due_date:
            return 0
        seconds_overdue = (now - obj.due_date).total_seconds()
        return round(seconds_overdue / (24 * 60 * 60), 2)
    
    def get_minutes_overdue(self, obj):
        """Calculate minutes overdue"""
        from django.utils import timezone
        if obj.status == 'PAID':
            return 0
        now = timezone.now()
        if now <= obj.due_date:
            return 0
        seconds_overdue = (now - obj.due_date).total_seconds()
        return int(seconds_overdue / 60)
    
    def get_minutes_remaining(self, obj):
        """Get minutes remaining until due date"""
        from django.utils import timezone
        if obj.status in ['PAID', 'PENALTY_PAID']:
            return 0
        now = timezone.now()
        if now >= obj.due_date:
            return 0
        seconds_remaining = (obj.due_date - now).total_seconds()
        return round(seconds_remaining / 60, 2)
    
    def get_penalty_breakdown(self, obj):
        from django.utils import timezone
        if obj.status == 'PAID':
            return {
                'days_overdue': 0,
                'penalty_per_day': 0,
                'grace_period_days': 0,
                'total_penalty': 0,
                'base_amount': float(obj.amount),
                'total_due': float(obj.amount)
            }
        
        now = timezone.now()
        if now <= obj.due_date:
            return {
                'days_overdue': 0,
                'penalty_per_day': float(obj.fee_structure.penalty_per_day) if obj.fee_structure else 0,
                'grace_period_days': obj.fee_structure.grace_period_days if obj.fee_structure else 0,
                'total_penalty': 0,
                'base_amount': float(obj.amount),
                'total_due': float(obj.amount)
            }
        
        seconds_overdue = (now - obj.due_date).total_seconds()
        days_overdue = seconds_overdue / (24 * 60 * 60)
        penalty_days = max(0, days_overdue - (obj.fee_structure.grace_period_days if obj.fee_structure else 0))
        penalty_amount = penalty_days * (float(obj.fee_structure.penalty_per_day) if obj.fee_structure else 0)
        
        return {
            'days_overdue': round(days_overdue, 2),
            'minutes_overdue': int(seconds_overdue / 60),
            'penalty_per_day': float(obj.fee_structure.penalty_per_day) if obj.fee_structure else 0,
            'grace_period_days': obj.fee_structure.grace_period_days if obj.fee_structure else 0,
            'penalty_days': round(penalty_days, 2),
            'total_penalty': penalty_amount,
            'base_amount': float(obj.amount),
            'total_due': float(obj.amount) + penalty_amount
        }
    
    def get_can_take_exam(self, obj):
        from django.utils import timezone
        now = timezone.now()
        return now <= obj.due_date and obj.status != 'LOCKED'
    
    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None
    
    def get_payment_period_display(self, obj):
        if obj.fee_structure and obj.fee_structure.payment_period:
            return obj.fee_structure.payment_period.name
        return None
    
    def get_is_locked(self, obj):
        return obj.status == 'LOCKED'
    
    def get_can_access(self, obj):
        return obj.is_access_allowed()