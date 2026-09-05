# exams/management/commands/auto_submit_exams.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from exams.models import ExamAttempt

class Command(BaseCommand):
    help = 'Auto-submit exams where heartbeat has stopped for 15 seconds'
    
    def handle(self, *args, **options):
        self.stdout.write('🔍 Checking for expired heartbeats...')
        
        now = timezone.now()
        threshold = now - timezone.timedelta(seconds=15)
        
        # Find attempts where heartbeat hasn't been received
        attempts = ExamAttempt.objects.filter(
            status='IN_PROGRESS',
            last_heartbeat__lt=threshold
        )
        
        count = 0
        for attempt in attempts:
            attempt.status = 'SUBMITTED'
            attempt.end_time = now
            attempt.save()
            count += 1
            self.stdout.write(f'✅ Auto-submitted attempt {attempt.id}')
        
        self.stdout.write(self.style.SUCCESS(f'✅ Auto-submitted {count} exams'))