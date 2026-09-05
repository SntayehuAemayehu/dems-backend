# backend/analytics/management/commands/lock_overdue.py
# COMPLETE - Create this file

from django.core.management.base import BaseCommand
from django.utils import timezone
from analytics.models import StudentPaymentSchedule
from accounts.models import StudentProfile
from notifications.utils import send_notification
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Lock students with overdue payments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Lock a specific student by email'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview without making changes'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=0,
            help='Days overdue threshold (default: 0 = lock immediately after grace period)'
        )

    def handle(self, *args, **options):
        email = options.get('email')
        dry_run = options.get('dry_run', False)
        days_threshold = options.get('days', 0)
        
        self.stdout.write('🔒 Starting lock overdue students...')
        
        today = timezone.now().date()
        
        # Build queryset
        if email:
            try:
                student = StudentProfile.objects.get(user__email=email)
                schedules = StudentPaymentSchedule.objects.filter(
                    student=student,
                    status__in=['PENDING', 'OVERDUE']
                )
                self.stdout.write(f'📊 Checking student: {email}')
            except StudentProfile.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ Student not found: {email}'))
                return
        else:
            schedules = StudentPaymentSchedule.objects.filter(
                status__in=['PENDING', 'OVERDUE'],
                due_date__lt=today
            )
        
        self.stdout.write(f'📊 Found {schedules.count()} overdue schedules')
        
        if schedules.count() == 0:
            self.stdout.write(self.style.SUCCESS('✅ No overdue students found!'))
            return
        
        locked_count = 0
        already_locked = 0
        updated_count = 0
        errors = []
        
        for schedule in schedules:
            try:
                student = schedule.student
                days_overdue = schedule.days_overdue()
                grace_days = schedule.fee_structure.grace_period_days if schedule.fee_structure else 0
                
                # Check if should be locked (after grace period + threshold)
                should_lock = days_overdue > (grace_days + days_threshold)
                
                self.stdout.write(f'  👤 {student.user.email} - Due: {schedule.due_date} - {days_overdue} days overdue - Should lock: {should_lock}')
                
                if dry_run:
                    if should_lock and schedule.status != 'LOCKED':
                        self.stdout.write(self.style.WARNING(f'  🔒 [DRY RUN] Would lock: {student.user.email}'))
                        locked_count += 1
                    continue
                
                # ✅ Call the update_status method
                updated = schedule.update_status()
                
                if updated:
                    schedule.refresh_from_db()
                    if schedule.status == 'LOCKED':
                        locked_count += 1
                        self.stdout.write(self.style.WARNING(f'  🔒 LOCKED: {student.user.email}'))
                        
                        # Send notification
                        try:
                            send_notification(
                                recipient_user=student.user,
                                title='🔒 Account Locked - Payment Overdue',
                                message=f'''Your account has been locked due to overdue payment.

Amount Due: ETB {schedule.amount}
Penalty: ETB {schedule.penalty_amount}
Total Due: ETB {schedule.total_amount}
Days Overdue: {days_overdue}

Please make the payment to restore access to all services.
''',
                                notification_type='SYSTEM_ALERT',
                                link='/payments'
                            )
                            self.stdout.write(f'  📧 Notification sent to {student.user.email}')
                        except Exception as e:
                            self.stdout.write(f'  ⚠️ Failed to send notification: {e}')
                    else:
                        updated_count += 1
                        self.stdout.write(f'  ⚠️ Updated to: {schedule.status}')
                else:
                    if schedule.status == 'LOCKED':
                        already_locked += 1
                        self.stdout.write(f'  ⏭️ Already locked: {student.user.email}')
                    else:
                        self.stdout.write(f'  ⏭️ No change needed: {schedule.status}')
                        
            except Exception as e:
                errors.append(f'{schedule.student.user.email}: {str(e)}')
                self.stdout.write(self.style.ERROR(f'  ❌ Error: {str(e)}'))
        
        # Summary
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'\n📊 DRY RUN SUMMARY:\n'
                f'  🔒 Would lock: {locked_count}\n'
                f'  📋 No changes were made\n'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n📊 SUMMARY:\n'
                f'  🔒 Newly locked: {locked_count}\n'
                f'  🔄 Already locked: {already_locked}\n'
                f'  ⚠️ Updated but not locked: {updated_count}\n'
                f'  ❌ Errors: {len(errors)}\n'
            ))
        
        if errors:
            self.stdout.write(self.style.ERROR('Errors:'))
            for error in errors:
                self.stdout.write(f'  {error}')