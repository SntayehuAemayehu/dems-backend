# analytics/management/commands/create_payment_schedules.py - NEW FILE

from django.core.management.base import BaseCommand
from django.utils import timezone
from analytics.models import PaymentPeriod, StudentPaymentSchedule, FeeStructure
from accounts.models import StudentProfile
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Create payment schedules for all students'
    
    def add_arguments(self, parser):
        parser.add_argument('--period_id', type=int, help='Specific payment period ID')
        parser.add_argument('--student_id', type=int, help='Specific student ID')
        parser.add_argument('--department_id', type=int, help='Specific department ID')
        parser.add_argument('--force', action='store_true', help='Force recreation even if exists')
    
    def handle(self, *args, **options):
        period_id = options.get('period_id')
        student_id = options.get('student_id')
        department_id = options.get('department_id')
        force = options.get('force', False)
        
        # Get payment periods
        if period_id:
            periods = PaymentPeriod.objects.filter(id=period_id, is_active=True)
        else:
            periods = PaymentPeriod.objects.filter(is_active=True)
        
        if not periods.exists():
            self.stdout.write(self.style.ERROR('No active payment periods found'))
            return
        
        # Get students
        if student_id:
            students = StudentProfile.objects.filter(id=student_id, is_enrolled=True)
        elif department_id:
            try:
                from accounts.models import Department
                department = Department.objects.get(id=department_id)
                students = StudentProfile.objects.filter(department=department.name, is_enrolled=True)
            except:
                students = StudentProfile.objects.filter(is_enrolled=True)
        else:
            students = StudentProfile.objects.filter(is_enrolled=True)
        
        if not students.exists():
            self.stdout.write(self.style.ERROR('No students found'))
            return
        
        created_count = 0
        skipped_count = 0
        errors_count = 0
        
        for period in periods:
            for student in students:
                try:
                    # Get fee structure for student's department
                    fee_structure = FeeStructure.objects.filter(
                        department__name=student.department,
                        is_active=True
                    ).first()
                    
                    if not fee_structure:
                        self.stdout.write(self.style.WARNING(
                            f'No fee structure for {student.user.full_name} (department: {student.department})'
                        ))
                        continue
                    
                    # Check if schedule already exists
                    existing = StudentPaymentSchedule.objects.filter(
                        student=student,
                        fee_structure=fee_structure
                    ).first()
                    
                    if existing and not force:
                        skipped_count += 1
                        continue
                    
                    if existing and force:
                        existing.delete()
                    
                    # Determine period number
                    period_count = StudentPaymentSchedule.objects.filter(student=student).count()
                    period_number = period_count + 1
                    
                    # Calculate dates
                    today = timezone.now().date()
                    start_date = today
                    end_date = start_date + timezone.timedelta(days=fee_structure.payment_period.duration_months * 30)
                    due_date = start_date + timezone.timedelta(days=30)  # Due 30 days from start
                    
                    # Create schedule
                    schedule = StudentPaymentSchedule.objects.create(
                        student=student,
                        fee_structure=fee_structure,
                        period_number=period_number,
                        start_date=start_date,
                        end_date=end_date,
                        due_date=due_date,
                        amount=fee_structure.amount,
                        penalty_amount=Decimal('0.00'),
                        total_amount=fee_structure.amount,
                        status='PENDING'
                    )
                    
                    # Update student's current payment schedule
                    student.current_payment_schedule_id = schedule.id
                    student.save()
                    
                    created_count += 1
                    
                    self.stdout.write(self.style.SUCCESS(
                        f'✅ Created schedule for {student.user.full_name} - Period {period_number}'
                    ))
                    
                except Exception as e:
                    errors_count += 1
                    self.stdout.write(self.style.ERROR(
                        f'❌ Error creating schedule for {student.user.full_name}: {str(e)}'
                    ))
                    logger.error(f"Error creating schedule: {e}")
        
        self.stdout.write(self.style.SUCCESS(
            f'\n📊 SUMMARY:\n'
            f'  Created: {created_count}\n'
            f'  Skipped: {skipped_count}\n'
            f'  Errors: {errors_count}'
        ))