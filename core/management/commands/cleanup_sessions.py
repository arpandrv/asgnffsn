# core/management/commands/cleanup_sessions.py
# Create this file to automatically clean up stale sessions

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import SurveySession
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Clean up stale survey sessions that have been in progress too long'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=2,
            help='Sessions older than this many hours will be cleaned up (default: 2)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned up without actually deleting'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        dry_run = options['dry_run']
        
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        stale_sessions = SurveySession.objects.filter(
            status='in_progress',
            start_time__lt=cutoff_time
        ).select_related('farm', 'surveyor')
        
        count = stale_sessions.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('No stale sessions found.')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would clean up {count} stale sessions:')
            )
            for session in stale_sessions:
                self.stdout.write(
                    f'  - Session {session.session_id} on {session.farm.name} '
                    f'by {session.surveyor.username} '
                    f'(started {session.start_time})'
                )
        else:
            # Actually delete the sessions
            session_details = []
            for session in stale_sessions:
                session_details.append({
                    'id': str(session.session_id),
                    'farm': session.farm.name,
                    'user': session.surveyor.username,
                    'started': session.start_time
                })
            
            stale_sessions.delete()
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully cleaned up {count} stale sessions.')
            )
            
            # Log the cleanup for audit purposes
            logger.info(f'Cleaned up {count} stale sessions: {session_details}')
        
        self.stdout.write(
            f'Sessions are considered stale if in_progress for more than {hours} hours.'
        )