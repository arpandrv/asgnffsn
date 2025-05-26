from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Simple force clear of user data using raw SQL.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting simple force data deletion process."))

        try:
            with connection.cursor() as cursor:
                # Disable foreign key constraints
                cursor.execute("PRAGMA foreign_keys = OFF")
                self.stdout.write("Foreign key constraints disabled.")

                # Check and delete data
                tables_to_clear = [
                    ('core_observation', 'Observation'),
                    ('core_surveysession', 'SurveySession'),
                    ('core_surveillancecalculation', 'SurveillanceCalculation'),
                    ('core_farm', 'Farm'),
                    ('core_grower', 'Grower'),
                ]

                for table_name, display_name in tables_to_clear:
                    cursor.execute(f"DELETE FROM {table_name}")
                    count = cursor.rowcount
                    self.stdout.write(self.style.SUCCESS(f"Deleted {count} {display_name} records."))

                # Delete admin logs for non-superusers
                cursor.execute("DELETE FROM django_admin_log WHERE user_id IN (SELECT id FROM auth_user WHERE is_superuser = 0)")
                log_count = cursor.rowcount
                self.stdout.write(self.style.SUCCESS(f"Deleted {log_count} LogEntry records."))

                # Count non-superusers before deletion
                cursor.execute("SELECT COUNT(*) FROM auth_user WHERE is_superuser = 0")
                user_count_before = cursor.fetchone()[0]

                # Delete non-superuser users
                cursor.execute("DELETE FROM auth_user WHERE is_superuser = 0")
                user_count = cursor.rowcount
                self.stdout.write(self.style.SUCCESS(f"Deleted {user_count} non-superuser User accounts."))

                # Count remaining superusers
                cursor.execute("SELECT COUNT(*) FROM auth_user WHERE is_superuser = 1")
                superuser_count = cursor.fetchone()[0]
                self.stdout.write(self.style.NOTICE(f"{superuser_count} superuser account(s) remain."))

                # Re-enable foreign key constraints
                cursor.execute("PRAGMA foreign_keys = ON")
                self.stdout.write("Foreign key constraints re-enabled.")

            self.stdout.write(self.style.SUCCESS("All user data successfully deleted!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error occurred: {e}"))
            # Try to re-enable foreign keys
            try:
                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA foreign_keys = ON")
            except:
                pass 