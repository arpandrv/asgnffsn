import logging
from typing import Dict, Any, Optional, List, Tuple

from django.contrib.auth.models import User
from ..models import Farm, Grower, PlantType, SurveySession
from .geoscape_service import fetch_cadastral_boundary

logger = logging.getLogger(__name__)


def fetch_and_save_cadastral_boundary(farm: Farm) -> Tuple[bool, Optional[str]]:
    """
    Fetches a cadastral boundary from Geoscape and saves it to the farm.
    """
    if not farm.geoscape_address_id:
        logger.info(f"Farm {farm.id} ('{farm.name}') has no Geoscape address ID. Skipping boundary fetch.")
        return False, "No Geoscape address ID available for this farm to fetch boundary."
    
    logger.info(f"Attempting to fetch cadastral boundary for farm {farm.id} ('{farm.name}') using address ID: {farm.geoscape_address_id}")
    boundary_json = fetch_cadastral_boundary(farm.geoscape_address_id)

    if not boundary_json:
        logger.warning(f"Failed to fetch cadastral boundary from Geoscape for farm {farm.id}.")
        return False, "Failed to fetch cadastral boundary from Geoscape."
    
    farm.boundary = boundary_json
    farm.save(update_fields=['boundary'])
    logger.info(f"Successfully fetched and saved cadastral boundary for farm {farm.id}.")
    return True, "Successfully fetched and saved cadastral boundary."


def get_user_farms(user: User) -> List[Farm]:
    """
    Retrieves all farms for a user.
    """
    try:
        grower = user.grower_profile
        return list(Farm.objects.filter(owner=grower).order_by('name'))
    except Grower.DoesNotExist:
        logger.warning(f"No grower profile found for user {user.username}")
        return []
    except Exception as e:
        logger.exception(f"Error retrieving farms for user {user.username}: {e}")
        return []


def get_farm_details(farm_id: int, user: User) -> Tuple[Optional[Farm], Optional[str]]:
    """
    Retrieves a farm by ID with access control check.
    """
    try:
        grower = user.grower_profile
        farm = Farm.objects.get(id=farm_id, owner=grower)
        return farm, None
    except Farm.DoesNotExist:
        logger.warning(f"Farm with id {farm_id} not found or not owned by user {user.username}.")
        return None, "Farm not found or you don't have permission to access it."
    except Grower.DoesNotExist:
        logger.warning(f"No grower profile found for user {user.username} when accessing farm {farm_id}.")
        return None, "User profile not found."
    except Exception as e:
        logger.exception(f"Error retrieving farm {farm_id} for user {user.username}: {e}")
        return None, f"An unexpected error occurred: {e}"


def create_farm(farm_data: Dict[str, Any], user: User) -> Tuple[Optional[Farm], Optional[str]]:
    """
    Creates a new farm for a user.
    """
    try:
        grower = user.grower_profile
        
        farm = Farm(owner=grower)
        
        direct_set_fields = ['name', 'region', 'geoscape_address_id', 'formatted_address', 'size_hectares', 'stocking_rate']
        for field in direct_set_fields:
            if field in farm_data:
                setattr(farm, field, farm_data[field])
        
        if not hasattr(farm, 'plant_type') or not farm.plant_type:
            try:
                mango_type, created = PlantType.objects.get_or_create(name='Mango')
                farm.plant_type = mango_type
                if created:
                    logger.info("Default 'Mango' PlantType created.")
            except Exception as e:
                logger.error(f"Error fetching/creating default 'Mango' PlantType: {e}")
                return None, "Error setting default plant type. Please ensure 'Mango' PlantType exists or can be created."
        
        farm.save()
        logger.info(f"Farm '{farm.name}' (ID: {farm.id}) created for user {user.username}.")
        
        if farm.geoscape_address_id:
            logger.info(f"Farm {farm.id} has Geoscape ID {farm.geoscape_address_id}. Attempting to fetch boundary.")
            success, message = fetch_and_save_cadastral_boundary(farm)
            if success:
                logger.info(f"Successfully fetched boundary for new farm {farm.id}.")
            else:
                logger.warning(f"Could not fetch boundary for new farm {farm.id}: {message}")
        else:
            logger.info(f"Farm {farm.id} created without a Geoscape address ID. No boundary fetched.")
            
        return farm, None
    
    except Grower.DoesNotExist:
        logger.error(f"Grower profile not found for user {user.username} during farm creation.")
        return None, "Grower profile not found. Cannot create farm."
    except Exception as e:
        logger.exception(f"Error creating farm for user {user.username}: {e}")
        return None, f"An unexpected error occurred during farm creation: {e}"


def update_farm(farm_id: int, farm_data: Dict[str, Any], user: User) -> Tuple[Optional[Farm], Optional[str]]:
    """
    Updates an existing farm.
    """
    farm, error = get_farm_details(farm_id, user)
    if error:
        return None, error
    
    try:
        original_geoscape_id = farm.geoscape_address_id
        address_id_changed = False

        direct_set_fields = ['name', 'region', 'geoscape_address_id', 'formatted_address', 'size_hectares', 'stocking_rate']
        for field in direct_set_fields:
            if field in farm_data:
                if field == 'geoscape_address_id' and getattr(farm, field) != farm_data[field]:
                    address_id_changed = True
                setattr(farm, field, farm_data[field])
        
        if 'plant_type' not in farm_data and (not farm.plant_type or farm.plant_type.name != 'Mango'):
            try:
                mango_type, _ = PlantType.objects.get_or_create(name='Mango')
                farm.plant_type = mango_type
            except Exception as e:
                logger.error(f"Error ensuring 'Mango' PlantType during farm update: {e}")

        farm.save()
        logger.info(f"Farm '{farm.name}' (ID: {farm.id}) updated by user {user.username}.")

        new_geoscape_id_present = bool(farm.geoscape_address_id)
        
        if new_geoscape_id_present and (address_id_changed or not farm.boundary):
            logger.info(f"Geoscape ID for farm {farm.id} changed or boundary missing. Attempting to fetch/update boundary.")
            success, message = fetch_and_save_cadastral_boundary(farm)
            if success:
                logger.info(f"Successfully fetched/updated boundary for farm {farm.id}.")
            else:
                logger.warning(f"Could not fetch/update boundary for farm {farm.id}: {message}")
                if address_id_changed and farm.boundary:
                    logger.info(f"Clearing outdated boundary for farm {farm.id} as address ID changed and new fetch failed.")
                    farm.boundary = None
                    farm.save(update_fields=['boundary'])

        elif not new_geoscape_id_present and original_geoscape_id:
            logger.info(f"Geoscape ID removed for farm {farm.id}. Clearing boundary.")
            farm.boundary = None
            farm.save(update_fields=['boundary'])
            
        return farm, None
    
    except Exception as e:
        logger.exception(f"Error updating farm {farm_id} for user {user.username}: {e}")
        return None, f"An unexpected error occurred during farm update: {e}"


def delete_farm(farm_id: int, user: User) -> Tuple[bool, Optional[str]]:
    """
    Deletes a farm.
    """
    farm, error = get_farm_details(farm_id, user)
    if error:
        return False, error
    
    try:
        farm_name = farm.name
        farm.delete()
        logger.info(f"Farm '{farm_name}' (ID: {farm_id}) deleted by user {user.username}.")
        return True, f"Farm '{farm_name}' deleted successfully."
    
    except Exception as e:
        logger.exception(f"Error deleting farm {farm_id} for user {user.username}: {e}")
        return False, f"An unexpected error occurred during farm deletion: {e}"


def get_farm_survey_sessions(farm_id: int, user: User, limit: int = None) -> Tuple[Optional[List[SurveySession]], Optional[str]]:
    """
    Retrieves survey sessions for a farm.
    """
    farm, error = get_farm_details(farm_id, user)
    if error:
        return None, error

    try:
        sessions_qs = SurveySession.objects.filter(farm=farm).order_by('-start_time')
        if limit:
            sessions_qs = sessions_qs[:limit]
        return list(sessions_qs), None

    except Exception as e:
        logger.exception(f"Error retrieving survey sessions for farm {farm_id}: {e}")
        return None, f"An unexpected error occurred: {e}"