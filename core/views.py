from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import models
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone
from django.urls import reverse
from .season_utils import get_seasonal_stage_info, get_surveillance_frequency
import json
from decimal import Decimal
from datetime import datetime, timedelta
from django.views.decorators.http import require_POST

from .forms import (
    SignUpForm, FarmForm, 
    UserEditForm, GrowerProfileEditForm, CalculatorForm, ObservationForm
)
from .models import (
    Farm, PlantType,
    Pest, Disease,
    Grower, Region, SurveillanceCalculation, SurveySession, Observation,
    User, SeasonalStage
)

from .services.user_service import create_user_with_profile
from .services.farm_service import (
    get_user_farms, get_farm_details, create_farm,
    update_farm, delete_farm,
    fetch_and_save_cadastral_boundary
)
from .services.calculation_service import save_calculation_to_database

from .services.surveillance_service import (
    create_observation, get_surveillance_recommendations,
)
from .services.geoscape_service import search_addresses

from .season_utils import get_seasonal_stage_info
from .calculations import calculate_surveillance_effort, DEFAULT_CONFIDENCE

import logging
logger = logging.getLogger(__name__)


def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user_data = form.cleaned_data 
            user, error = create_user_with_profile(user_data)
            if user:
                login(request, user)
                messages.success(request, f"Welcome to Mango Surveillance Hub, {user.username}!")
                return redirect('core:dashboard')
            else:
                messages.error(request, error or "Could not create account. Please try again.")
        else:
            pass
    else:
        form = SignUpForm()
    return render(request, 'core/signup.html', {'form': form})


@login_required
def home_view(request):
    farms = get_user_farms(request.user)
    sorted_farms = sorted(farms, key=lambda f: (f.days_since_last_surveillance() is None, f.name))
    return render(request, 'core/home.html', {'farms': sorted_farms})


@login_required
def create_farm_view(request):
    if request.method == 'POST':
        form = FarmForm(request.POST)
        if form.is_valid():
            farm_data = form.cleaned_data
            farm, error = create_farm(farm_data, request.user)
            
            if farm:
                messages.success(request, f"Farm '{farm.name}' was created successfully!")
                return redirect('core:farm_detail', farm_id=farm.id)
            else:
                messages.error(request, error or "Could not create farm.")
    else:
        form = FarmForm()
    
    return render(request, 'core/create_farm.html', {'form': form})


@login_required
def farm_detail_view(request, farm_id):
    farm, error = get_farm_details(farm_id, request.user)
    if error:
        messages.error(request, error)
        return redirect('core:myfarms')

    recommendations = get_surveillance_recommendations(farm)
    
    calculation_results = None
    try:
        latest_calc = SurveillanceCalculation.objects.filter(farm=farm, is_current=True).latest('date_created')
        calculation_results = latest_calc.to_dict()
        calculation_results['error'] = None
        logger.info(f"Farm Detail: Displaying saved calculation ID {latest_calc.id} for farm {farm.id}")
    except SurveillanceCalculation.DoesNotExist:
        logger.info(f"Farm Detail: No saved calculation for farm {farm.id}. Calculating with default confidence.")
        if recommendations.get('stage_name') != 'Unknown' and farm.total_plants():
            seasonal_info = get_seasonal_stage_info(farm.region.name if farm.region else None)
            prevalence_p_for_calc = seasonal_info.get('prevalence_p')

            if prevalence_p_for_calc is not None:
                calculation_results = calculate_surveillance_effort(
                    farm=farm,
                    confidence_level_percent=DEFAULT_CONFIDENCE,
                    prevalence_p=prevalence_p_for_calc 
                )
            else:
                calculation_results = {'error': "Could not determine prevalence for current stage."}
        else:
            calculation_results = {'error': "Farm details (plants) or seasonal stage missing for calculation."}
    except Exception as e:
        logger.error(f"Farm Detail: Error fetching/calculating for display: {e}")
        calculation_results = {'error': f"Error retrieving calculation: {e}"}

    completed_sessions = SurveySession.objects.filter(
        farm=farm,
        status='completed'
    ).order_by('-end_time')[:5]

    latest_in_progress = SurveySession.objects.filter(
        farm=farm,
        status__in=['not_started', 'in_progress']
    ).order_by('-start_time').first()

    context = {
        'farm': farm,
        'current_stage': recommendations.get('stage_name'),
        'month_used_for_stage': recommendations.get('month_used'),
        'calculation_results': calculation_results,
        'completed_sessions': completed_sessions,
        'latest_in_progress': latest_in_progress,
        'priority_pests': recommendations.get('priority_pests'),
        'priority_diseases': recommendations.get('priority_diseases'),
        'recommended_parts': recommendations.get('recommended_parts'),
        'surveillance_frequency': get_surveillance_frequency(),
        'last_surveillance_date': farm.last_surveillance_date(),
        'next_due_date': farm.next_due_date(),
        'farm_boundary_json': farm.boundary
    }
    
    return render(request, 'core/farm_detail.html', context)


@login_required
def edit_farm_view(request, farm_id):
    farm, error = get_farm_details(farm_id, request.user)
    if error:
        messages.error(request, error)
        return redirect('core:myfarms')
    
    if request.method == 'POST':
        form = FarmForm(request.POST, instance=farm)
        if form.is_valid():
            farm_data = form.cleaned_data
            updated_farm, error = update_farm(farm_id, farm_data, request.user)
            if error:
                messages.error(request, error)
            else:
                messages.success(request, f"Farm '{updated_farm.name}' was updated successfully!")
                return redirect('core:farm_detail', farm_id=updated_farm.id)
    else:
        form = FarmForm(instance=farm)
    
    context = {
        'form': form,
        'farm': farm,
        'is_edit': True
    }
    return render(request, 'core/create_farm.html', context)


@login_required
def delete_farm_view(request, farm_id):
    farm, error = get_farm_details(farm_id, request.user)
    if error:
        messages.error(request, error)
        return redirect('core:myfarms')
    
    if request.method == 'POST':
        farm_name = farm.name
        success, message = delete_farm(farm_id, request.user)
        if success:
            messages.success(request, message or f"Farm '{farm_name}' deleted.")
            return redirect('core:myfarms')
        else:
            messages.error(request, message or "Could not delete farm.")
            return redirect('core:farm_detail', farm_id=farm.id)
    
    return render(request, 'core/delete_farm_confirm.html', {'farm': farm})


@login_required
def calculator_view(request):
    grower = request.user.grower_profile
    calculation_results = None
    selected_farm_instance = None
    form_submitted = False
    
    initial_farm_id = request.GET.get('farm')
    initial_region_name = None
    if initial_farm_id:
        try:
            initial_farm_for_region = Farm.objects.get(id=initial_farm_id, owner=grower)
            if initial_farm_for_region.region:
                initial_region_name = initial_farm_for_region.region.name
        except Farm.DoesNotExist:
            pass

    stage_info = get_seasonal_stage_info()
    current_stage = stage_info.get('stage_name', "Unknown")
    current_prevalence_p = stage_info.get('prevalence_p')
    month_used_for_calc = stage_info.get('month_used')
    
    current_pests_qs = Pest.objects.filter(name__in=stage_info.get('pest_names', [])).order_by('name')
    current_diseases_qs = Disease.objects.filter(name__in=stage_info.get('disease_names', [])).order_by('name')

    if request.GET and 'farm' in request.GET and 'confidence_level' in request.GET:
        form_submitted = True
        form = CalculatorForm(grower, request.GET)
        if form.is_valid():
            selected_farm_instance = form.cleaned_data['farm']
            confidence_level_percent = int(form.cleaned_data['confidence_level'])
            
            if current_prevalence_p is not None and selected_farm_instance.total_plants() is not None:
                calculation_results = calculate_surveillance_effort(
                    farm=selected_farm_instance,
                    confidence_level_percent=confidence_level_percent,
                    prevalence_p=current_prevalence_p
                )
                if not calculation_results.get('error'):
                    calculation_results['season'] = current_stage
                    saved_calc = save_calculation_to_database(calculation_results, selected_farm_instance, request.user)
                    if saved_calc:
                        messages.success(request, f"Surveillance calculation saved for {selected_farm_instance.name}.")
                    else:
                        messages.error(request, "Could not save calculation results.")
                else:
                     messages.error(request, f"Calculation Error: {calculation_results.get('error')}")
            else:
                error_msg = "Cannot calculate: "
                if current_prevalence_p is None: error_msg += "Seasonal prevalence not available. "
                if selected_farm_instance.total_plants() is None: error_msg += "Farm plant count not available. "
                calculation_results = {'error': error_msg.strip()}
                messages.error(request, calculation_results['error'])
    else:
        form = CalculatorForm(grower, initial={'farm': initial_farm_id} if initial_farm_id else {})

    context = {
        'form': form,
        'selected_farm': selected_farm_instance,
        'calculation_results': calculation_results,
        'form_submitted': form_submitted,
        'current_stage': current_stage,
        'current_prevalence_p': float(current_prevalence_p * 100) if current_prevalence_p is not None else None,
        'month_used_for_calc': month_used_for_calc,
        'current_pests': current_pests_qs,
        'current_diseases': current_diseases_qs,
    }
    return render(request, 'core/calculator.html', context)


@login_required
def profile_view(request):
    user_form = UserEditForm(instance=request.user)
    try:
        grower_profile = request.user.grower_profile
    except Grower.DoesNotExist:
        grower_profile = Grower.objects.create(user=request.user, farm_name="Default Farm Name")
        messages.warning(request, "Grower profile was missing and has been created with default values. Please update.")

    profile_form = GrowerProfileEditForm(instance=grower_profile)

    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=request.user)
        profile_form = GrowerProfileEditForm(request.POST, instance=grower_profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('core:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }
    return render(request, 'core/profile.html', context)


@login_required
def record_list_view(request):
    grower = request.user.grower_profile
    completed_sessions = SurveySession.objects.filter(
        farm__owner=grower,
        status='completed'
    ).select_related('farm', 'surveyor').order_by('-end_time')

    farms_with_sessions = Farm.objects.filter(
        owner=grower, 
        survey_sessions__status='completed'
    ).annotate(
        session_count=Count('survey_sessions', filter=models.Q(survey_sessions__status='completed'))
    ).filter(session_count__gt=0).order_by('name')

    sessions_by_farm = {
        farm: completed_sessions.filter(farm=farm) for farm in farms_with_sessions
    }
    all_farms = Farm.objects.filter(owner=grower).order_by('name')

    context = {
        'farms': all_farms,
        'sessions_by_farm': sessions_by_farm,
        'completed_sessions': completed_sessions
    }
    return render(request, 'core/record_list.html', context)


@login_required
def dashboard_view(request):
    grower = request.user.grower_profile
    farms = list(get_user_farms(request.user))
    
    surveillance_count = SurveySession.objects.filter(farm__owner=grower, status='completed').count()
    latest_session = SurveySession.objects.filter(farm__owner=grower, status='completed').order_by('-end_time').first()
    
    total_plants = grower.total_plants_managed()
    
    recent_sessions = SurveySession.objects.filter(farm__owner=grower, status='completed').select_related('farm').order_by('-end_time')[:5]
    
    due_farms = [farm for farm in farms if farm.next_due_date() <= timezone.now().date()]
    due_farms_count = len(due_farms)
    
    seasonal_info = get_seasonal_stage_info()
    current_season_stage_name = seasonal_info.get('stage_name', 'Unknown')
    month_used = seasonal_info.get('month_used')
    
    month_names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    season_label = f"Current month: {month_names[month_used-1]}" if month_used else "Season: Unknown"
    
    context = {
        'grower': grower,
        'surveillance_count': surveillance_count,
        'latest_record': latest_session,
        'total_plants': total_plants,
        'recent_records': recent_sessions,
        'due_farms': due_farms,
        'due_farms_count': due_farms_count,
        'current_season': current_season_stage_name,
        'season_label': season_label,
        'seasonal_info': seasonal_info 
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def address_suggestion_view(request):
    if 'debug' in request.GET:
        return HttpResponse("Address API Debug page content would be here.")

    query = request.GET.get('query', '')
    region_id_str = request.GET.get('region_id')
    suggestions = []
    error_message = None
    state_territory_used = None

    if not region_id_str:
        error_message = "Region must be selected first."
    else:
        try:
            region_id = int(region_id_str)
            selected_region = Region.objects.get(id=region_id)
            state_territory_used = selected_region.state_abbreviation
            
            if not state_territory_used:
                error_message = f"State/Territory not configured for region: {selected_region.name}."
            elif query and len(query) >= 3:
                suggestions = search_addresses(query, state_territory_used)
                if not suggestions:
                    error_message = "No address suggestions found. Try a different search term."
            elif not query or len(query) < 3:
                 error_message = "Please type at least 3 characters to search for an address."

        except Region.DoesNotExist:
            error_message = "Invalid region selected."
        except ValueError:
            error_message = "Invalid region ID format."
        except Exception as e:
            logger.error(f"Error in address suggestion: {e}", exc_info=True)
            error_message = "An error occurred while processing the address search."

    response_data = {'suggestions': suggestions if not error_message else []}
    if error_message:
        response_data['error'] = error_message
    if state_territory_used:
        response_data['state_territory_used'] = state_territory_used
        
    return JsonResponse(response_data)


@login_required
def start_survey_session_view(request, farm_id):
    farm, error = get_farm_details(farm_id, request.user)
    if error:
        messages.error(request, error)
        return redirect('core:myfarms') 

    existing_session = SurveySession.objects.filter(
        farm=farm, 
        surveyor=request.user, 
        status__in=['in_progress', 'not_started']
    ).order_by('-start_time').first()

    if existing_session:
        messages.info(request, f"Resuming existing survey session for {farm.name}.")
        return redirect('core:active_survey_session', session_id=existing_session.session_id)

    target_plants = None
    try:
        latest_calc = SurveillanceCalculation.objects.filter(farm=farm, is_current=True).latest('date_created')
        target_plants = latest_calc.required_plants
    except SurveillanceCalculation.DoesNotExist:
        logger.info(f"StartSession: No current calculation found for farm {farm.id}. Target plants will be None.")
    except Exception as e:
        logger.error(f"StartSession: Error fetching calculation for farm {farm.id}: {e}")

    try:
        new_session = SurveySession.objects.create(
            farm=farm,
            surveyor=request.user,
            status='in_progress',
            start_time=timezone.now(),
            target_plants_surveyed=target_plants
        )
        messages.success(request, f"New survey session started for {farm.name}.")
        return redirect('core:active_survey_session', session_id=new_session.session_id)
    except Exception as e:
        messages.error(request, f"Could not start a new survey session: {e}")
        logger.error(f"StartSession: Error creating SurveySession for farm {farm.id}: {e}", exc_info=True)
        return redirect('core:farm_detail', farm_id=farm.id)


@login_required
def active_survey_session_view(request, session_id):
    session = get_object_or_404(SurveySession, session_id=session_id, surveyor=request.user)
    if session.status == 'completed' or session.status == 'abandoned':
        messages.info(request, f"Session for {session.farm.name} is already {session.status}. Viewing details instead.")
        return redirect('core:survey_session_detail', session_id=session.session_id)

    farm = session.farm
    
    recommendations = get_surveillance_recommendations(farm)
    
    observations = Observation.objects.filter(
        session=session, 
        status='completed'
    ).select_related().order_by('-observation_time')
    
    observation_count = observations.count()
    target_plants = session.target_plants_surveyed or 0
    progress_percent = int((observation_count / target_plants) * 100) if target_plants > 0 else 0
    progress_percent = min(max(progress_percent, 0), 100)

    unique_pests_count = Pest.objects.filter(observations__in=observations).distinct().count()
    unique_diseases_count = Disease.objects.filter(observations__in=observations).distinct().count()
    
    context = {
        'session': session,
        'farm': farm,
        'observations': observations,
        'form': ObservationForm(),
        'observation_count': observation_count,
        'completed_plants': observation_count,
        'target_plants': target_plants,
        'progress_percent': progress_percent,
        'completion_percentage': progress_percent,
        'unique_pests_count': unique_pests_count,
        'unique_diseases_count': unique_diseases_count,
        'recommended_pests_ids': [p.id for p in recommendations.get('priority_pests', [])],
        'recommended_diseases_ids': [d.id for d in recommendations.get('priority_diseases', [])],
        'recommended_pests': recommendations.get('priority_pests'),
        'recommended_diseases': recommendations.get('priority_diseases'),
        'recommended_parts': recommendations.get('recommended_parts'),
        'current_stage_name': recommendations.get('stage_name', 'Unknown'),
    }
    return render(request, 'core/active_survey_session.html', context)


@require_POST
@login_required
def create_observation_api(request):
    logger.debug(f"create_observation_api called with POST data: {request.POST}")
    form = ObservationForm(request.POST)
    session_id = request.POST.get('session_id')

    if not session_id:
        logger.error("create_observation_api: Session ID missing in POST data.")
        return JsonResponse({'status': 'error', 'message': 'Session ID is required.'}, status=400)

    try:
        session = SurveySession.objects.get(session_id=session_id, surveyor=request.user)
        if not session.is_active():
            logger.warning(f"Attempt to add observation to inactive session {session_id}.")
            return JsonResponse({'status': 'error', 'message': 'This survey session is no longer active.'}, status=400)
    except SurveySession.DoesNotExist:
        logger.error(f"create_observation_api: Survey session {session_id} not found for user {request.user.username}.")
        return JsonResponse({'status': 'error', 'message': 'Survey session not found.'}, status=404)

    if form.is_valid():
        observation_data = form.cleaned_data
        observation_data['pests_observed'] = list(form.cleaned_data['pests_observed'].values_list('id', flat=True))
        observation_data['diseases_observed'] = list(form.cleaned_data['diseases_observed'].values_list('id', flat=True))

        obs, error = create_observation(session, observation_data)
        if obs:
            logger.info(f"Observation {obs.id} created successfully for session {session.id}.")
            obs_data_for_js = obs.to_dict()
            obs_data_for_js['time'] = obs.observation_time.strftime('%I:%M %p')

            return JsonResponse({
                'status': 'success',
                'message': 'Observation saved.',
                'observation': obs_data_for_js,
                'observation_count': session.observation_count(),
                'unique_pests': session.get_unique_pests().count(),
                'unique_diseases': session.get_unique_diseases().count()
            })
        else:
            logger.error(f"Error creating observation via service for session {session.id}: {error}")
            return JsonResponse({'status': 'error', 'message': error or "Could not save observation."}, status=500)
    else:
        logger.warning(f"Observation form invalid for session {session.id}: {form.errors.as_json()}")
        return JsonResponse({'status': 'error', 'message': 'Invalid data.', 'errors': form.errors.get_json_data()}, status=400)


@require_POST
@login_required
def finish_survey_session_api(request, session_id):
    try:
        session = SurveySession.objects.get(session_id=session_id, surveyor=request.user)
    except SurveySession.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Survey session not found.'}, status=404)
    
    if not session.is_active():
        return JsonResponse({'status': 'error', 'message': f'Session is already {session.get_status_display()}.'}, status=400)
        
    if session.observation_count() == 0 and session.target_plants_surveyed > 0:
        return JsonResponse({'status': 'error', 'message': 'Cannot complete session with no observations recorded when a target was set.'}, status=400)
            
    session.status = 'completed'
    session.end_time = timezone.now()
    session.save(update_fields=['status', 'end_time'])
    logger.info(f"Session {session_id} marked as completed.")
    
    redirect_url = reverse('core:survey_session_detail', kwargs={'session_id': session_id})
    return JsonResponse({
        'status': 'success',
        'message': 'Survey session completed successfully.',
        'redirect_url': redirect_url,
        'session_summary': session.summarize()
    })


@login_required
def survey_session_list_view(request, farm_id):
    farm = get_object_or_404(Farm, id=farm_id, owner=request.user.grower_profile)
    sessions = SurveySession.objects.filter(farm=farm).annotate(
        observation_count=Count('observations', filter=models.Q(observations__status='completed'))
    ).order_by('-start_time')
    context = {
        'farm': farm,
        'sessions': sessions,
    }
    return render(request, 'core/survey_session_list.html', context)


@login_required
def survey_session_detail_view(request, session_id):
    session = get_object_or_404(SurveySession.objects.select_related('farm', 'surveyor'), 
                                session_id=session_id, surveyor=request.user)
    
    observations = Observation.objects.filter(
        session=session, status='completed'
    ).prefetch_related(
        'pests_observed', 
        'diseases_observed'
    ).order_by('observation_time')
    
    completed_count = observations.count()
    unique_pests = Pest.objects.filter(observations__in=observations).distinct()
    unique_diseases = Disease.objects.filter(observations__in=observations).distinct()

    context = {
        'session': session,
        'farm': session.farm,
        'observations': observations,
        'completed_count': completed_count,
        'unique_pests_count': unique_pests.count(),
        'unique_diseases_count': unique_diseases.count(),
        'unique_pests': unique_pests,
        'unique_diseases': unique_diseases,
        'farm_boundary_json': session.farm.boundary,
    }
    return render(request, 'core/survey_session_detail.html', context)


@login_required
def delete_survey_session_view(request, session_id):
    session = get_object_or_404(SurveySession, session_id=session_id, surveyor=request.user)
    farm = session.farm

    if session.status not in ['not_started', 'in_progress']:
        messages.error(request, "Only ongoing or unstarted sessions can be deleted. Completed sessions are part of the record.")
        return redirect('core:survey_session_list', farm_id=farm.id)

    if request.method == 'POST':
        start_time_str = session.start_time.strftime('%Y-%m-%d %H:%M')
        obs_count = session.observation_count()
        
        session.delete()
        
        messages.success(request, f"Survey session from {start_time_str} (had {obs_count} recorded observations) was deleted.")
        return redirect('core:survey_session_list', farm_id=farm.id)
    
    messages.warning(request, "Invalid request to delete session.")
    return redirect('core:survey_session_list', farm_id=farm.id)