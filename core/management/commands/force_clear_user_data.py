from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.admin.models import LogEntry
from django.db import connection, transaction
from core.models import (
    Observation, 
    SurveySession, 
    SurveillanceCalculation, 
    Farm, 
    Grower
)

class Command(BaseCommand):
    help = 'Force removes all user-CRUDable data by temporarily disabling foreign key constraints (SQLite only).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting FORCE data deletion process. This is irreversible."))
        self.stdout.write(self.style.WARNING("This command disables foreign key constraints temporarily."))

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # Disable foreign key constraints for SQLite
                    cursor.execute("PRAGMA foreign_keys = OFF;")
                    self.stdout.write("Foreign key constraints disabled.")

                    # Get non-superuser IDs for reference
                    non_superuser_ids = list(User.objects.filter(is_superuser=False).values_list('id', flat=True))
                    
                    if not non_superuser_ids:
                        self.stdout.write(self.style.NOTICE("No non-superusers found to process."))
                        return
                    else:
                        self.stdout.write(f"Found {len(non_superuser_ids)} non-superuser(s) to delete.")

                    # Delete data using Django ORM (foreign keys disabled so should work)
                    self.stdout.write("Deleting Observation data...")
                    obs_count, _ = Observation.objects.all().delete()
                    self.stdout.write(self.style.SUCCESS(f"Successfully deleted {obs_count} Observation records."))

                    self.stdout.write("Deleting SurveySession data...")
                    ss_count, _ = SurveySession.objects.all().delete()
                    self.stdout.write(self.style.SUCCESS(f"Successfully deleted {ss_count} SurveySession records."))

                    self.stdout.write("Deleting SurveillanceCalculation data...")
                    sc_count, _ = SurveillanceCalculation.objects.all().delete()
                    self.stdout.write(self.style.SUCCESS(f"Successfully deleted {sc_count} SurveillanceCalculation records."))

                    self.stdout.write("Deleting Farm data...")
                    farm_count, _ = Farm.objects.all().delete()
                    self.stdout.write(self.style.SUCCESS(f"Successfully deleted {farm_count} Farm records."))

                    self.stdout.write("Deleting Grower data...")
                    grower_count, _ = Grower.objects.all().delete()
                    self.stdout.write(self.style.SUCCESS(f"Successfully deleted {grower_count} Grower records."))

                    self.stdout.write("Deleting LogEntry records for non-superusers...")
                    log_count, _ = LogEntry.objects.filter(user_id__in=non_superuser_ids).delete()
                    self.stdout.write(self.style.SUCCESS(f"Successfully deleted {log_count} LogEntry records."))

                    self.stdout.write("Force deleting non-superuser User accounts...")
                    user_count, _ = User.objects.filter(id__in=non_superuser_ids).delete()
                    self.stdout.write(self.style.SUCCESS(f"Successfully force deleted {user_count} non-superuser User accounts."))

                    # Re-enable foreign key constraints
                    cursor.execute("PRAGMA foreign_keys = ON;")
                    self.stdout.write("Foreign key constraints re-enabled.")
                
                superusers_kept = User.objects.filter(is_superuser=True).count()
                self.stdout.write(self.style.NOTICE(f"{superusers_kept} superuser account(s) have been kept."))

            self.stdout.write(self.style.SUCCESS("All specified data has been successfully FORCE deleted."))
            self.stdout.write(self.style.NOTICE("Kept data in: Disease, Pest, PlantPart, PlantType, Region, SeasonalStage."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {e}"))
            self.stdout.write(self.style.ERROR("Force deletion process failed and was rolled back."))
            
            # Ensure foreign keys are back on even if there was an error
            try:
                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA foreign_keys = ON;")
                    self.stdout.write("Foreign key constraints have been re-enabled after error.")
            except:
                self.stdout.write(self.style.ERROR("Could not re-enable foreign key constraints. Manual intervention may be required.")) 