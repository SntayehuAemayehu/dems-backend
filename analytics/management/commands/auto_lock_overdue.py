# analytics/management/commands/auto_lock_overdue.py
# COMPLETE - Run this daily to lock overdue students

from django.core.management.base import BaseCommand
from django.utils import timezone
from analytics.models import StudentPaymentSchedule
from accounts.models import StudentProfile
from notifications.utils import send_notification
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Auto-lock students with overdue payments'

    def handle(self, *args, **options):
        self.stdout.write('🔒 Starting auto-lock for overdue students...')
        
        # Get all overdue schedules
        today = timezone.now().date()
        overdue_schedules = StudentPaymentSchedule.objects.filter(
            status__in=['PENDING', 'OVERDUE'],
            due_date__lt=today
        )
        
        locked_count = 0
        notified_count = 0
        skipped_count = 0
        
        for schedule in overdue_schedules:
            student = schedule.student
            
            # ✅ Call update_status - this is the key!
            updated = schedule.update_status()
            
            if updated and schedule.status == 'LOCKED':
                locked_count += 1
                
                # Send notification
                try:
                    send_notification(
                        recipient_user=student.user,
                        title='🔒 Account Locked - Payment Overdue',
                        message=f'''Your account has been locked due to overdue payment.

Amount Due: ETB {schedule.amount}
Penalty: ETB {schedule.penalty_amount}
Total Due: ETB {schedule.total_amount}
Days Overdue: {schedule.days_overdue()}

Please make the payment to restore access to all services.
''',
                        notification_type='SYSTEM_ALERT',
                        link='/payments'
                    )
                    notified_count += 1
                except Exception as e:
                    self.stdout.write(f'⚠️ Failed to notify {student.user.email}: {e}')
                
                self.stdout.write(f'🔒 Locked: {student.user.email} - {schedule.days_overdue()} days overdue')
            
            elif updated:
                self.stdout.write(f'⚠️ Updated to OVERDUE: {student.user.email}')
            else:
                skipped_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'✅ Auto-lock complete!\n'
            f'   🔒 Locked: {locked_count}\n'
            f'   📧 Notified: {notified_count}\n'
            f'   ⏭️ Skipped: {skipped_count}'
        ))