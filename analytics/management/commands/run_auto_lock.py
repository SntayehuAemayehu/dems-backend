# analytics/management/commands/run_auto_lock.py

from django.core.management.base import BaseCommand
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Run auto-lock for overdue students'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Running auto-lock for overdue students...'))
        
        try:
            # ✅ Call the lock command with threshold 0 (lock immediately after grace period)
            call_command('lock_overdue_students', days_threshold=0)
            self.stdout.write(self.style.SUCCESS('✅ Auto-lock completed successfully'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Auto-lock failed: {str(e)}'))
            logger.error(f'Auto-lock failed: {e}')