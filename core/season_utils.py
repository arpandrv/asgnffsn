import datetime
from decimal import Decimal
from django.db.models import Q
from .models import SeasonalStage, Pest, Disease, PlantPart

def get_seasonal_stage_info():
    """
    Determines the farming stage and associated data (prevalence, pests, diseases)
    by querying the SeasonalStage model based on the current month.
    Dynamically determines the recommended plant parts based on the parts affected 
    by the active pests and diseases for the found stage.

    Returns:
        dict: {
            'stage_name': str or None, 
            'prevalence_p': Decimal or None,
            'pest_names': list[str], 
            'disease_names': list[str], 
            'part_names': list[str],
            'month_used': int
        }
        Returns None for stage_name and prevalence_p, and empty lists for names
        if no matching stage is found in the database.
    """
    month_to_use = datetime.datetime.now().month

    current_stage = None
    try:
        # Find stages where the current month number is in the comma-separated 'months' string.
        stages = SeasonalStage.objects.filter(
            Q(months__startswith=f"{month_to_use},") | # Starts with month,
            Q(months__endswith=f",{month_to_use}") |   # Ends with ,month
            Q(months__contains=f",{month_to_use},") | # Contains ,month,
            Q(months=str(month_to_use))              # Is exactly month (for single-month stages)
        ).prefetch_related('active_pests__affects_plant_parts', 'active_diseases__affects_plant_parts')
        
        if stages.exists():
            # In case a month is accidentally assigned to multiple stages, pick the first one found.
            current_stage = stages.first()
        else:
             print(f"Warning (get_seasonal_stage_info): No SeasonalStage found in database for month {month_to_use}.")

    except Exception as e:
        print(f"Error (get_seasonal_stage_info): Database query failed - {e}")
        current_stage = None

    result = {
        'stage_name': None,
        'prevalence_p': None,
        'pest_names': [],
        'disease_names': [],
        'part_names': [],
        'month_used': month_to_use
    }

    if current_stage:
        result['stage_name'] = current_stage.name
        result['prevalence_p'] = current_stage.prevalence_p
        
        active_pests = current_stage.active_pests.all()
        active_diseases = current_stage.active_diseases.all()
        result['pest_names'] = list(active_pests.values_list('name', flat=True))
        result['disease_names'] = list(active_diseases.values_list('name', flat=True))

        recommended_parts_set = set()
        
        for pest in active_pests:
            for part in pest.affects_plant_parts.all():
                recommended_parts_set.add(part.name)
                
        for disease in active_diseases:
            for part in disease.affects_plant_parts.all():
                recommended_parts_set.add(part.name)
                
        result['part_names'] = sorted(list(recommended_parts_set))

    return result

def get_surveillance_frequency():
    """
        Returns: Number of days between surveillance checks (always 7)
    """
    return 7  # Weekly surveillance for all stages