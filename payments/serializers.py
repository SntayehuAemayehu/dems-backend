# payments/serializers.py - COMPLETE FIXED

from rest_framework import serializers
from .models import PaymentProof, Invoice

# payments/serializers.py - UPDATE PaymentProofSerializer

class PaymentProofSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    verified_by_name = serializers.SerializerMethodField()
    receipt_url = serializers.SerializerMethodField()
    rolled_back_by_name = serializers.SerializerMethodField()
    can_rollback = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentProof
        fields = [
            'id', 'student', 'student_name', 'student_id', 'payment_type',
            'amount', 'bank_name', 'transaction_id', 'transaction_date',
            'receipt_image', 'receipt_url', 'status', 'verified_by', 'verified_by_name',
            'verified_at', 'rejection_reason', 'semester', 'academic_year',
            'uploaded_at',
            # ✅ ROLLBACK FIELDS
            'is_rolled_back', 'rolled_back_by', 'rolled_back_by_name', 'rolled_back_at',
            'rollback_reason', 'original_status', 'can_rollback'
        ]
        read_only_fields = ['uploaded_at', 'verified_at', 'status', 'student', 'receipt_image']
    
    def get_student_name(self, obj):
        return obj.student.user.full_name if obj.student and obj.student.user else None
    
    def get_student_id(self, obj):
        return obj.student.student_id if obj.student else None
    
    def get_verified_by_name(self, obj):
        return obj.verified_by.full_name if obj.verified_by else None
    
    def get_receipt_url(self, obj):
        if obj.receipt_image and hasattr(obj.receipt_image, 'url'):
            return obj.receipt_image.url
        return None
    
    def get_rolled_back_by_name(self, obj):
        return obj.rolled_back_by.full_name if obj.rolled_back_by else None
    
    def get_can_rollback(self, obj):
        """Check if payment can be rolled back"""
        return obj.status in ['VERIFIED', 'PENDING'] and not obj.is_rolled_back

class InvoiceSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = '__all__'
    
    def get_student_name(self, obj):
        return obj.student.user.full_name if obj.student and obj.student.user else None