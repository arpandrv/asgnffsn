from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Force removes all user-CRUDable data using raw SQL (SQLite only).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting RAW SQL FORCE data deletion process. This is irreversible."))
        self.stdout.write(self.style.WARNING("This command uses raw SQL and disables foreign key constraints."))

        try:
            with connection.cursor() as cursor:
                # Disable foreign key constraints for SQLite
                cursor.execute("PRAGMA foreign_keys = OFF;")
                self.stdout.write("Foreign key constraints disabled.")

                # Get count of non-superusers before deletion
                cursor.execute("SELECT COUNT(*) FROM auth_user WHERE is_superuser = 0;")
                non_superuser_count = cursor.fetchone()[0]
                self.stdout.write(f"Found {non_superuser_count} non-superuser(s) to delete.")

                if non_superuser_count == 0:
                    self.stdout.write(self.style.NOTICE("No non-superusers found to process."))
                    return

                # Get non-superuser IDs for log cleanup
                cursor.execute("SELECT id FROM auth_user WHERE is_superuser = 0;")
                non_superuser_ids = [row[0] for row in cursor.fetchall()]

                # Delete data using raw SQL in dependency order
                
                # 1. Delete Observations
                cursor.execute("DELETE FROM core_observation;")
                obs_count = cursor.rowcount
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted {obs_count} Observation records."))

                # 2. Delete SurveySessions
                cursor.execute("DELETE FROM core_surveysession;")
                ss_count = cursor.rowcount
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted {ss_count} SurveySession records."))

                # 3. Delete SurveillanceCalculations
                cursor.execute("DELETE FROM core_surveillancecalculation;")
                sc_count = cursor.rowcount
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted {sc_count} SurveillanceCalculation records."))

                # 4. Delete Farms
                cursor.execute("DELETE FROM core_farm;")
                farm_count = cursor.rowcount
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted {farm_count} Farm records."))

                # 5. Delete Growers
                cursor.execute("DELETE FROM core_grower;")
                grower_count = cursor.rowcount
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted {grower_count} Grower records."))

                # 6. Delete LogEntries for non-superusers
                if non_superuser_ids:
                    placeholders = ','.join(['?' for _ in non_superuser_ids])
                    cursor.execute(f"DELETE FROM django_admin_log WHERE user_id IN ({placeholders})", non_superuser_ids)
                    log_count = cursor.rowcount
                    self.stdout.write(self.style.SUCCESS(f"Successfully deleted {log_count} LogEntry records."))

                # 7. Delete non-superuser Users
                cursor.execute("DELETE FROM auth_user WHERE is_superuser = 0;")
                user_count = cursor.rowcount
                self.stdout.write(self.style.SUCCESS(f"Successfully force deleted {user_count} non-superuser User accounts."))

                # Re-enable foreign key constraints
                cursor.execute("PRAGMA foreign_keys = ON;")
                self.stdout.write("Foreign key constraints re-enabled.")

                # Check remaining superusers
                cursor.execute("SELECT COUNT(*) FROM auth_user WHERE is_superuser = 1;")
                superuser_count = cursor.fetchone()[0]
                self.stdout.write(self.style.NOTICE(f"{superuser_count} superuser account(s) have been kept."))

            self.stdout.write(self.style.SUCCESS("All specified data has been successfully RAW FORCE deleted."))
            self.stdout.write(self.style.NOTICE("Kept data in: Disease, Pest, PlantPart, PlantType, Region, SeasonalStage."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {e}"))
            self.stdout.write(self.style.ERROR("Raw force deletion process failed."))
            
            # Ensure foreign keys are back on even if there was an error
            try:
                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA foreign_keys = ON;")
                    self.stdout.write("Foreign key constraints have been re-enabled after error.")
            except:
                self.stdout.write(self.style.ERROR("Could not re-enable foreign key constraints. Manual intervention may be required.")) 