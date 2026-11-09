from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from .models import Notification
from .serializers import NotificationSerializer
from rest_framework.permissions import IsAdminUser
from accounts.models import User
# ✅ UPDATED IMPORTS: Added the new SMS functions
from .sms_service import send_bulk_same_message, send_bulk_personalized


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        try:
            notification = Notification.objects.get(id=pk, recipient=request.user)
        except Notification.DoesNotExist:
            return Response({'error': 'Notification not found'}, status=status.HTTP_404_NOT_FOUND)
        
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return Response({'message': 'Marked as read'})


class NotificationMarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True, read_at=timezone.now())
        return Response({'message': 'All notifications marked as read'})


class UnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({'unread_count': count})


# ============================================================
# ✅ NEW: BULK SMS VIEW (Add this to the bottom of the file)
# ============================================================
class SendBulkSMSView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        message_type = request.data.get('type', 'same')
        base_message = request.data.get('message', '')
        student_ids = request.data.get('student_ids', []) # ✅ NEW: Get IDs from frontend
        
        # Filter by specific IDs if provided, otherwise fallback to all
        if student_ids:
            students = User.objects.filter(id__in=student_ids).exclude(phone='')
        else:
            students = User.objects.filter(role='STUDENT').exclude(phone='')

        if not students.exists():
            return Response({"error": "No students selected or missing phone numbers."}, status=400)

        if message_type == "same":
            phones = [student.phone for student in students]
            result = send_bulk_same_message(phones, base_message)
            if result:
                return Response({"success": True, "message": f"Queued for {len(phones)} students."})
            return Response({"error": "Failed to queue SMS."}, status=500)

        elif message_type == "personal":
            messages_data = []
            for student in students:
                # Inserts the student's name into the message
                personalized_text = f"Hi {student.full_name}, {base_message}"
                messages_data.append({
                    "recipients": [student.phone],
                    "message": personalized_text
                })
            result = send_bulk_personalized(messages_data)
            if result:
                return Response({"success": True, "message": f"Sent personalized messages to {len(messages_data)} students."})
            return Response({"error": "Failed to queue personalized SMS."}, status=500)

        return Response({"error": "Invalid type."}, status=400)