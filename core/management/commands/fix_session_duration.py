from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import SurveySession

class Command(BaseCommand):
    help = 'Fix sessions with unrealistic durations'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find sessions with problematic durations
        problematic = []
        for session in SurveySession.objects.filter(status='completed'):
            duration = session.duration()
            if duration and (duration < 0 or duration > 1440):  # Less than 0 or more than 24 hours
                problematic.append(session)
        
        if not problematic:
            self.stdout.write(self.style.SUCCESS('No problematic sessions found!'))
            return
        
        self.stdout.write(f'Found {len(problematic)} sessions with unrealistic durations:')
        
        for session in problematic:
            old_duration = session.duration()
            obs_count = session.observation_count()
            
            if dry_run:
                self.stdout.write(f'  Session {session.session_id}: {old_duration} minutes ({obs_count} observations)')
            else:
                # Fix by setting reasonable end time
                estimated_minutes = max(10, obs_count * 2)  # 2 min per observation, min 10
                session.end_time = session.start_time + timedelta(minutes=estimated_minutes)
                session.save(update_fields=['end_time'])
                new_duration = session.duration()
                self.stdout.write(f'  Fixed session {session.session_id}: {old_duration} → {new_duration} minutes')
        
        if dry_run:
            self.stdout.write('\nRun without --dry-run to fix these sessions')
        else:
            self.stdout.write(f'\nFixed {len(problematic)} sessions!')