import logging
from django.utils import timezone
from ..models import SurveillanceCalculation, Farm
from django.contrib.auth.models import User
from decimal import Decimal

logger = logging.getLogger(__name__)

def save_calculation_to_database(calculation_result: dict, farm: Farm, user: User) -> SurveillanceCalculation | None:
    """
    Saves a calculation result to the database.
    Ensures only one calculation is marked as 'is_current' for a farm.
    """
    if not calculation_result or calculation_result.get('error'):
        error_msg = calculation_result.get('error', 'Unknown error') if calculation_result else 'Missing calculation result'
        logger.error(f"Cannot save calculation with error for farm {farm.id if farm else 'Unknown'}: {error_msg}")
        return None
    
    try:
        SurveillanceCalculation.objects.filter(farm=farm, is_current=True).update(is_current=False)
        
        prevalence_p_percent = Decimal(str(calculation_result.get('prevalence_p', 0.0))) * Decimal('100.0')
        margin_of_error_percent = Decimal(str(calculation_result.get('margin_of_error', 0.0))) * Decimal('100.0')
        percentage_total = calculation_result.get('percentage_of_total')
        calc = SurveillanceCalculation(
            farm=farm,
            created_by=user,
            season=calculation_result.get('season', 'Unknown'),
            confidence_level=int(calculation_result['confidence_level_percent']),
            population_size=int(calculation_result['N']),
            prevalence_percent=prevalence_p_percent.quantize(Decimal('0.01')),
            margin_of_error=margin_of_error_percent.quantize(Decimal('0.01')),
            required_plants=int(calculation_result['required_plants_to_survey']),
            percentage_of_total=Decimal(str(percentage_total)).quantize(Decimal('0.01')) if percentage_total is not None else None,
            survey_frequency=calculation_result.get('survey_frequency'),
            is_current=True,
            notes=calculation_result.get('notes', None)
        )
        calc.save()
        logger.info(f"Successfully saved new calculation (ID: {calc.id}) for farm {farm.id}, marked as current.")
        return calc
    except KeyError as ke:
        logger.error(f"Missing expected key in calculation_result for farm {farm.id}: {ke}. Data: {calculation_result}")
        return None
    except Exception as e:
        logger.exception(f"Error saving calculation to database for farm {farm.id}: {e}")
        return None