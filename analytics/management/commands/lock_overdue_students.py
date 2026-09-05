# analytics/management/commands/lock_overdue_students.py
# COMPLETE AUTO-LOCK COMMAND

from django.core.management.base import BaseCommand
from django.utils import timezone
from analytics.models import StudentPaymentSchedule, StudentAccessLog
from accounts.models import StudentProfile
from notifications.utils import send_notification
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Lock students with overdue payments and send notifications'
    
    def add_arguments(self, parser):
        parser.add_argument('--days_threshold', type=int, default=0, 
                            help='Days overdue before locking (default: 0 = lock immediately after due date + grace period)')
        parser.add_argument('--dry_run', action='store_true', 
                            help='Preview without making changes')
        parser.add_argument('--student_id', type=int, help='Specific student ID')
    
    def handle(self, *args, **options):
        days_threshold = options.get('days_threshold', 0)
        dry_run = options.get('dry_run', False)
        student_id = options.get('student_id')
        
        # Build queryset - find all schedules that are overdue
        if student_id:
            schedules = StudentPaymentSchedule.objects.filter(
                student_id=student_id,
                status__in=['PENDING', 'OVERDUE']
            )
        else:
            schedules = StudentPaymentSchedule.objects.filter(
                status__in=['PENDING', 'OVERDUE'],
                due_date__lt=timezone.now().date()
            )
        
        locked_count = 0
        notified_count = 0
        already_locked_count = 0
        skipped_count = 0
        updated_count = 0
        
        self.stdout.write(self.style.WARNING(
            f'🔍 Scanning for overdue payments (threshold: {days_threshold} days)'
        ))
        self.stdout.write(f'📅 Current date: {timezone.now().date()}')
        self.stdout.write(f'📊 Found {schedules.count()} overdue schedules\n')
        
        for schedule in schedules:
            student = schedule.student
            days_overdue = schedule.days_overdue()
            grace_days = schedule.fee_structure.grace_period_days if schedule.fee_structure else 0
            
            self.stdout.write(f'  👤 {student.user.full_name} - Due: {schedule.due_date} - Overdue: {days_overdue} days')
            
            if days_overdue <= 0:
                skipped_count += 1
                continue
            
            # ✅ Check if should be locked
            # Lock after grace period + threshold
            effective_threshold = grace_days + days_threshold
            
            if days_overdue > effective_threshold:
                if dry_run:
                    self.stdout.write(self.style.WARNING(
                        f'  🔒 [DRY RUN] Would lock {student.user.full_name} - {days_overdue} days overdue'
                    ))
                    locked_count += 1
                    continue
                
                # ✅ Update status to LOCKED
                if schedule.status != 'LOCKED':
                    # Calculate penalty
                    schedule.penalty_amount = schedule.calculate_penalty()
                    schedule.total_amount = schedule.amount + schedule.penalty_amount
                    schedule.status = 'LOCKED'
                    schedule.locked_at = timezone.now()
                    schedule.save()
                    
                    # ✅ Update student's payment status
                    student.payment_status = 'OVERDUE_LOCKED'
                    student.save()
                    
                    locked_count += 1
                    
                    # ✅ Send notification to student
                    try:
                        send_notification(
                            recipient_user=student.user,
                            title='🔒 Account Locked - Payment Overdue',
                            message=f'''Your account has been locked due to overdue payment.

Payment Period: Period {schedule.period_number}
Due Date: {schedule.due_date}
Amount Due: ETB {schedule.amount}
Penalty: ETB {schedule.penalty_amount}
Total Due: ETB {schedule.total_amount}
Days Overdue: {days_overdue}

Please make the payment to restore access to all services.
''',
                            notification_type='SYSTEM_ALERT',
                            link='/payments'
                        )
                        notified_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  ⚠️ Failed to send notification: {e}'))
                    
                    # ✅ Log the lock
                    try:
                        StudentAccessLog.objects.create(
                            student=student,
                            access_type='LOGIN',
                            allowed=False,
                            reason=f'Account locked due to overdue payment ({days_overdue} days)',
                            ip_address='SYSTEM'
                        )
                    except:
                        pass
                    
                    self.stdout.write(self.style.WARNING(
                        f'  🔒 Locked {student.user.full_name} - {days_overdue} days overdue'
                    ))
                else:
                    already_locked_count += 1
                    self.stdout.write(f'  ⚠️ Already locked: {student.user.full_name}')
            else:
                # ✅ Update to OVERDUE if not already
                if schedule.status != 'OVERDUE':
                    schedule.status = 'OVERDUE'
                    schedule.penalty_amount = schedule.calculate_penalty()
                    schedule.total_amount = schedule.amount + schedule.penalty_amount
                    schedule.save()
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠️ {student.user.full_name} - {days_overdue} days overdue (penalty: ETB {schedule.penalty_amount})'
                    ))
                else:
                    # Update penalty amount
                    new_penalty = schedule.calculate_penalty()
                    if new_penalty != schedule.penalty_amount:
                        schedule.penalty_amount = new_penalty
                        schedule.total_amount = schedule.amount + new_penalty
                        schedule.save()
                        self.stdout.write(f'  💰 Updated penalty for {student.user.full_name}: ETB {new_penalty}')
        
        # Summary
        self.stdout.write(self.style.SUCCESS(
            f'\n📊 SUMMARY:\n'
            f'  🔒 Locked: {locked_count}\n'
            f'  🔄 Already locked: {already_locked_count}\n'
            f'  📧 Notifications sent: {notified_count}\n'
            f'  ⚠️ Updated to OVERDUE: {updated_count}\n'
            f'  ⏭️ Skipped (not overdue): {skipped_count}\n'
            f'  {"📋 [DRY RUN - No changes made]" if dry_run else "✅ [Changes applied]"}'
        ))