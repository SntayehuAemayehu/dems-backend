# proctoring/serializers.py - COMPLETE FIXED VERSION

from rest_framework import serializers
from .models import ProctorImage, ProctorLog, ProctorSession

class ProctorImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProctorImage
        fields = '__all__'
        read_only_fields = ['capture_time', 'image']


class ProctorLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProctorLog
        fields = '__all__'
        read_only_fields = ['timestamp']


class ProctorSessionSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    exam_title = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    
    class Meta:
        model = ProctorSession
        fields = '__all__'
    
    def get_student_name(self, obj):
        if obj.attempt and obj.attempt.student:
            return obj.attempt.student.user.full_name
        return None
    
    def get_student_id(self, obj):
        if obj.attempt and obj.attempt.student:
            return obj.attempt.student.student_id
        return None
    
    def get_exam_title(self, obj):
        if obj.attempt and obj.attempt.exam:
            return obj.attempt.exam.title
        return None