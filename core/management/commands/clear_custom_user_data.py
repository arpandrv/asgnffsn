from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.admin.models import LogEntry
from core.models import (
    Observation, 
    SurveySession, 
    SurveillanceCalculation, 
    Farm, 
    Grower
    # We don't need to import Disease, Pest, PlantPart, PlantType, Region, SeasonalStage
    # as we are not deleting data from them.
)
from django.db import transaction

class Command(BaseCommand):
    help = 'Removes all user-CRUDable data except for superusers and specified lookup tables.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting data deletion process. This is irreversible."))

        try:
            with transaction.atomic():
                self.stdout.write("Identifying non-superusers for LogEntry cleanup and deletion...")
                non_superuser_ids = list(User.objects.filter(is_superuser=False).values_list('id', flat=True))
                
                if not non_superuser_ids:
                    self.stdout.write(self.style.NOTICE("No non-superusers found to process."))
                else:
                    self.stdout.write(f"Found {len(non_superuser_ids)} non-superuser(s).")

                # Delete in order of dependency
                self.stdout.write("Deleting Observation data...")
                # Filter observations by sessions linked to non-superusers if necessary,
                # but deleting all is simpler if that's the goal for these dependent models.
                # For now, we delete all as per original request.
                obs_count, _ = Observation.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted {obs_count} Observation records."))

                self.stdout.write("Deleting SurveySession data...")
                # Filter by non-superusers if sessions should only be deleted if they belong to non-superusers
                # sessions_to_delete = SurveySession.objects.filter(surveyor_id__in=non_superuser_ids)
                # For now, we delete all as per original request.
                ss_count, _ = SurveySession.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted {ss_count} SurveySession records."))

                self.stdout.write("Deleting SurveillanceCalculation data...")
                # Filter by non-superusers if calculations should only be deleted if created_by non-superusers
                # calcs_to_delete = SurveillanceCalculation.objects.filter(created_by_id__in=non_superuser_ids)
                # For now, we delete all as per original request.
                sc_count, _ = SurveillanceCalculation.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted {sc_count} SurveillanceCalculation records."))

                self.stdout.write("Deleting Farm data...")
                # Farms are linked to Growers. Growers are linked to Users.
                # If we only want to delete farms of non-superusers:
                # farms_to_delete = Farm.objects.filter(owner__user_id__in=non_superuser_ids)
                # For now, we delete all as per original request.
                farm_count, _ = Farm.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted {farm_count} Farm records."))

                self.stdout.write("Deleting Grower data...")
                # Filter by non-superusers
                # growers_to_delete = Grower.objects.filter(user_id__in=non_superuser_ids)
                # For now, we delete all as per original request for simplicity, assuming if a user is gone, their grower profile should be too.
                # However, the User deletion step will handle non-superusers.
                # Let's refine to delete only growers associated with non-superusers to be more precise before user deletion.
                grower_count, _ = Grower.objects.filter(user_id__in=non_superuser_ids).delete()
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted {grower_count} Grower records linked to non-superusers."))
                
                # Also delete any Grower records that might be orphaned if their user was somehow deleted
                # without CASCADE working as expected or if they are linked to no user (though OneToOneField implies a user).
                # This is more of a cleanup for robustness.
                orphaned_growers, _ = Grower.objects.filter(user__isnull=True).delete()
                if orphaned_growers > 0:
                    self.stdout.write(self.style.NOTICE(f"Cleaned up {orphaned_growers} orphaned Grower records."))


                if non_superuser_ids:
                    self.stdout.write("Deleting LogEntry records for non-superusers...")
                    log_count, _ = LogEntry.objects.filter(user_id__in=non_superuser_ids).delete()
                    self.stdout.write(self.style.SUCCESS(f"Successfully deleted {log_count} LogEntry records for non-superusers."))

                    self.stdout.write("Deleting non-superuser User accounts...")
                    user_count, _ = User.objects.filter(id__in=non_superuser_ids).delete()
                    self.stdout.write(self.style.SUCCESS(f"Successfully deleted {user_count} non-superuser User accounts."))
                
                superusers_kept = User.objects.filter(is_superuser=True).count()
                self.stdout.write(self.style.NOTICE(f"{superusers_kept} superuser account(s) have been kept."))

            self.stdout.write(self.style.SUCCESS("All specified data has been successfully deleted."))
            self.stdout.write(self.style.NOTICE("Kept data in: Disease, Pest, PlantPart, PlantType, Region, SeasonalStage."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {e}"))
            self.stdout.write(self.style.ERROR("Data deletion process failed and was rolled back due to transaction.atomic().")) 