import logging
from typing import Dict, Any, Optional, List, Tuple
from django.utils import timezone

from ..models import Farm, PlantPart, Pest, Disease, SurveySession, Observation
from ..season_utils import get_seasonal_stage_info

logger = logging.getLogger(__name__)


def create_observation(
    session: SurveySession,
    data: Dict[str, Any]
) -> Tuple[Optional[Observation], Optional[str]]:
    """Creates a new completed observation within a survey session."""
    try:
        observation = Observation(
            session=session,
            observation_time=timezone.now(),
            status='completed'
        )

        for field in ['notes', 'plant_sequence_number']:
            if field in data:
                setattr(observation, field, data[field])
        
        if not data.get('plant_sequence_number'):
            last_obs = Observation.objects.filter(session=session).order_by('-plant_sequence_number').first()
            observation.plant_sequence_number = (last_obs.plant_sequence_number + 1) if last_obs and last_obs.plant_sequence_number is not None else 1

        observation.save()

        pest_ids = data.get('pests_observed', [])
        if pest_ids:
            observation.pests_observed.set(pest_ids)

        disease_ids = data.get('diseases_observed', [])
        if disease_ids:
            observation.diseases_observed.set(disease_ids)
        
        logger.info(f"Observation {observation.id} created for session {session.session_id}.")
        return observation, None

    except Exception as e:
        logger.exception(f"Error creating observation for session {session.session_id}: {e}")
        return None, f"An unexpected error occurred while creating observation: {e}"


def get_surveillance_recommendations(farm: Farm) -> Dict[str, Any]:
    """Gets surveillance recommendations for a farm based on the current seasonal stage."""
    seasonal_data = get_seasonal_stage_info() 

    stage_name = seasonal_data.get('stage_name', 'Unknown')
    month_used = seasonal_data.get('month_used')
    
    priority_pests = Pest.objects.filter(name__in=seasonal_data.get('pest_names', [])).order_by('name')
    priority_diseases = Disease.objects.filter(name__in=seasonal_data.get('disease_names', [])).order_by('name')
    recommended_parts = PlantPart.objects.filter(name__in=seasonal_data.get('part_names', [])).order_by('name')

    last_date = farm.last_surveillance_date()
    next_due = farm.next_due_date()
    current_farm_season = farm.current_season() 

    logger.info(f"Recommendations for farm {farm.id}: Stage='{stage_name}', MonthUsed={month_used}, Pests={priority_pests.count()}, Diseases={priority_diseases.count()}, Parts={recommended_parts.count()}")

    return {
        'season': current_farm_season, 
        'stage_name': stage_name,
        'month_used': month_used,
        'priority_pests': priority_pests,
        'priority_diseases': priority_diseases,
        'recommended_parts': recommended_parts,
        'last_surveillance_date': last_date,
        'next_due_date': next_due,
    }


def get_surveillance_stats(farm: Farm) -> Dict[str, Any]:
    """Gets surveillance statistics for a farm."""
    total_sessions = SurveySession.objects.filter(farm=farm, status='completed').count()

    total_observations = Observation.objects.filter(
        session__farm=farm,
        session__status='completed',
        status='completed'
    ).count()

    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    recent_sessions = SurveySession.objects.filter(
        farm=farm,
        status='completed',
        end_time__gte=thirty_days_ago
    ).count()

    from django.db.models import Count
    common_pests = Pest.objects.filter(
        observations__session__farm=farm,
        observations__status='completed'
    ).annotate(
        occurrence_count=Count('observations')
    ).order_by('-occurrence_count')[:5]
    
    common_diseases = Disease.objects.filter(
        observations__session__farm=farm,
        observations__status='completed'
    ).annotate(
        occurrence_count=Count('observations')
    ).order_by('-occurrence_count')[:5]

    logger.info(f"Stats for farm {farm.id}: TotalSessions={total_sessions}, TotalObs={total_observations}, RecentSessions={recent_sessions}")

    return {
        'total_sessions': total_sessions,
        'total_observations': total_observations,
        'recent_sessions': recent_sessions,
        'common_pests': common_pests,
        'common_diseases': common_diseases,
    }