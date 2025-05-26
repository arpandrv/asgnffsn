from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime
from decimal import Decimal
import uuid

# Constants for choices
DISTRIBUTION_CHOICES = [
    ('uniform', 'Uniform'),
    ('clustered', 'Clustered'),
    ('random', 'Random'),
]

SEASON_CHOICES = [
    ('Wet', 'Wet Season'),
    ('Dry', 'Dry Season'),
    ('Flowering', 'Flowering Period'),
]

CONFIDENCE_CHOICES = [
    (90, '90%'),
    (95, '95%'),
    (99, '99%'),
]

SURVEY_STATUS_CHOICES = [
    ('not_started', 'Not Started'),
    ('in_progress', 'In Progress'),
    ('completed', 'Completed'),
    ('abandoned', 'Abandoned'),
]

OBSERVATION_STATUS_CHOICES = [
    ('completed', 'Completed'),
]


class Grower(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='grower_profile')
    farm_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Profile ({self.farm_name})"
    
    def recent_survey_sessions(self, limit=5):
        return SurveySession.objects.filter(
            farm__owner=self,
            status='completed'
        ).select_related('farm').order_by('-end_time')[:limit]
    
    def total_plants_managed(self):
        from django.db.models import Sum, F, ExpressionWrapper, DecimalField
        
        farms_with_counts = self.farms.filter(
            size_hectares__isnull=False, 
            stocking_rate__isnull=False
        )
        
        total_expr = ExpressionWrapper(
            F('size_hectares') * F('stocking_rate'), 
            output_field=DecimalField()
        )
        
        result = farms_with_counts.aggregate(
            total=Sum(total_expr)
        )
        
        total = result['total']
        return int(total) if total is not None else None


class Region(models.Model):
    name = models.CharField(max_length=100, unique=True)
    climate_zone = models.CharField(max_length=50, blank=True, null=True)
    state_abbreviation = models.CharField(
        max_length=3, 
        blank=True, 
        null=True, 
        help_text="State/Territory abbreviation (e.g., NT, QLD, WA)"
    )

    def __str__(self):
        return self.name


class PlantType(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Plant Type"
        verbose_name_plural = "Plant Types"

    def __str__(self):
        return self.name
        
    def get_farms(self):
        return self.farms.all()
        
    def get_pests(self):
        return self.pests.all()
        
    def get_diseases(self):
        return self.diseases.all()


class PlantPart(models.Model):
    name = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Plant Part"
        verbose_name_plural = "Plant Parts"

    def __str__(self):
        return self.name
        
    def get_pests(self):
        return self.pests.all()
        
    def get_diseases(self):
        return self.diseases.all()


class Pest(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    affects_plant_types = models.ManyToManyField(PlantType, related_name='pests', blank=True)
    affects_plant_parts = models.ManyToManyField(PlantPart, related_name='pests', blank=True)

    def __str__(self):
        return self.name
    
    @classmethod
    def get_priority_pests_for_season(cls, season, plant_type=None):
        queryset = cls.objects.all()
        if plant_type:
            queryset = queryset.filter(affects_plant_types=plant_type)
        
        if season == 'Wet':
            queryset = queryset.order_by('name')
        else: 
            queryset = queryset.order_by('-name')
            
        return queryset[:3]


class Disease(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    affects_plant_types = models.ManyToManyField(PlantType, related_name='diseases', blank=True)
    affects_plant_parts = models.ManyToManyField(PlantPart, related_name='diseases', blank=True)

    def __str__(self):
        return self.name
    
    @classmethod
    def get_priority_diseases_for_season(cls, season, plant_type=None):
        queryset = cls.objects.all()
        if plant_type:
            queryset = queryset.filter(affects_plant_types=plant_type)

        if season == 'Wet':
            queryset = queryset.order_by('-name')
        else: 
            queryset = queryset.order_by('name')
            
        return queryset[:3]


class SeasonalStage(models.Model):
    name = models.CharField(max_length=100, unique=True)
    months = models.CharField(max_length=50)
    prevalence_p = models.DecimalField(max_digits=4, decimal_places=3)
    active_pests = models.ManyToManyField(Pest, related_name='seasonal_stages', blank=True)
    active_diseases = models.ManyToManyField(Disease, related_name='seasonal_stages', blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['id'] 
        verbose_name = "Seasonal Stage Mapping"
        verbose_name_plural = "Seasonal Stage Mappings"


class Farm(models.Model):
    owner = models.ForeignKey(Grower, on_delete=models.CASCADE, related_name='farms', db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, related_name='farms')
    size_hectares = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stocking_rate = models.IntegerField(null=True, blank=True)
    plant_type = models.ForeignKey(PlantType, on_delete=models.SET_NULL, null=True, blank=True, related_name='farms')
    geoscape_address_id = models.CharField(max_length=50, blank=True, null=True, unique=True, db_index=True)
    formatted_address = models.CharField(max_length=500, blank=True, null=True)
    boundary = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['owner']),
            models.Index(fields=['plant_type']),
            models.Index(fields=['region']),
            models.Index(fields=['geoscape_address_id']),
        ]

    def __str__(self):
        return self.name
    
    def total_plants(self):
        if self.size_hectares is None or self.stocking_rate is None:
            return None
        return int(float(self.size_hectares) * self.stocking_rate)
    
    def current_season(self):
        current_month = timezone.now().month
        season_map = {
            1: 'Wet', 2: 'Wet', 3: 'Wet',
            4: 'Flowering', 5: 'Flowering', 6: 'Flowering', 7: 'Flowering',
            8: 'Dry', 9: 'Dry', 10: 'Dry',
            11: 'Wet', 12: 'Wet'
        }
        return season_map.get(current_month, 'Unknown')
    
    def last_surveillance_date(self):
        latest = self.survey_sessions.filter(status='completed').order_by('-end_time').first()
        return latest.end_time if latest else None

    def days_since_last_surveillance(self):
        last_date = self.last_surveillance_date()
        if not last_date:
            return None
        if isinstance(last_date, datetime):
            last_date = last_date.date()
        today = timezone.now().date()
        return (today - last_date).days
    
    def next_due_date(self):
        last_date = self.last_surveillance_date()
        today = timezone.now().date()
        if not last_date:
            return today
        thirty_days_after = (last_date.date() if isinstance(last_date,  datetime) else last_date) + timezone.timedelta(days=30)
        return today if thirty_days_after <= today else thirty_days_after
    
    def active_survey_sessions(self):
        return self.survey_sessions.filter(status__in=['not_started', 'in_progress'])
    
    def completed_survey_sessions(self):
        return self.survey_sessions.filter(status='completed')
        
    def has_active_sessions(self):
        return self.active_survey_sessions().exists()
        
    def get_seasonal_recommendations(self):
        current_season = self.current_season()
        recommended_pests = Pest.get_priority_pests_for_season(current_season, self.plant_type)
        recommended_diseases = Disease.get_priority_diseases_for_season(current_season, self.plant_type)
        
        try:
            from django.db.models import Q
            current_month = timezone.now().month
            stage_query = Q(months__startswith=f"{current_month},") | \
                          Q(months__endswith=f",{current_month}") | \
                          Q(months__contains=f",{current_month},") | \
                          Q(months=str(current_month))
            stage = SeasonalStage.objects.filter(stage_query).first()
            
            plant_parts = []
            if stage and hasattr(stage, 'plant_parts_to_check'):
                plant_parts = stage.plant_parts_to_check.all()
            else:
                plant_parts = PlantPart.objects.all()[:3] 
                
        except Exception:
            plant_parts = PlantPart.objects.all()[:3]
            
        return {
            'pests': recommended_pests,
            'diseases': recommended_diseases,
            'plant_parts': plant_parts,
            'season': current_season
        }


class SurveillanceCalculation(models.Model):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='calculations', db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calculations', db_index=True)
    date_created = models.DateTimeField(default=timezone.now, db_index=True)
    season = models.CharField(max_length=20, choices=SEASON_CHOICES, db_index=True)
    confidence_level = models.IntegerField(choices=CONFIDENCE_CHOICES)
    population_size = models.IntegerField()
    prevalence_percent = models.DecimalField(max_digits=5, decimal_places=2)
    margin_of_error = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    required_plants = models.IntegerField()
    percentage_of_total = models.DecimalField(max_digits=5, decimal_places=2)
    survey_frequency = models.IntegerField(null=True, blank=True)
    is_current = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-date_created']
        verbose_name = "Surveillance Calculation"
        verbose_name_plural = "Surveillance Calculations"
        indexes = [
            models.Index(fields=['farm', '-date_created']),
            models.Index(fields=['farm', 'is_current']),
        ]

    def __str__(self):
        return f"{self.farm.name} calculation from {self.date_created.strftime('%Y-%m-%d')}"

    def save(self, *args, **kwargs):
        if self.is_current:
            SurveillanceCalculation.objects.filter(
                farm=self.farm, 
                is_current=True
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)
        
    def get_confidence_level_display_text(self):
        return f"{self.get_confidence_level_display()}% confidence"
        
    def get_prevalence_display_text(self):
        return f"{self.prevalence_percent}% prevalence"
        
    def to_dict(self):
        return {
            'id': self.id,
            'farm_id': self.farm.id,
            'farm_name': self.farm.name,
            'date_created': self.date_created,
            'season': self.season,
            'confidence_level': self.confidence_level,
            'confidence_level_percent': self.confidence_level,  # Add this for consistency
            'prevalence_percent': float(self.prevalence_percent),
            'margin_of_error': float(self.margin_of_error),
            'population_size': self.population_size,
            'N': self.population_size,  # Add this for consistency with calculate_surveillance_effort
            'required_plants': self.required_plants,
            'required_plants_to_survey': self.required_plants,  # Add this - template expects this key
            'percentage_of_total': float(self.percentage_of_total),
            'survey_frequency': self.survey_frequency,
            'is_current': self.is_current
        }


class SurveySessionManager(models.Manager):
    def active(self):
        return self.filter(status__in=['not_started', 'in_progress'])
        
    def completed(self):
        return self.filter(status='completed')
        
    def abandoned(self):
        return self.filter(status='abandoned')
        
    def by_farm(self, farm_id):
        return self.filter(farm_id=farm_id)
        
    def recent(self, limit=10):
        return self.all().order_by('-start_time')[:limit]


class SurveySession(models.Model):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='survey_sessions', db_index=True)
    surveyor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='survey_sessions', db_index=True)
    start_time = models.DateTimeField(default=timezone.now, db_index=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=SURVEY_STATUS_CHOICES, default='not_started', db_index=True)
    target_plants_surveyed = models.PositiveIntegerField(null=True, blank=True)
    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    
    objects = SurveySessionManager()

    class Meta:
        ordering = ['-start_time']
        verbose_name = "Survey Session"
        verbose_name_plural = "Survey Sessions"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['farm', 'status']),
            models.Index(fields=['surveyor', '-start_time']),
        ]
    
    def __str__(self):
        return f"Survey on {self.farm.name} ({self.start_time.strftime('%Y-%m-%d')})"

    def get_status_badge_class(self):
        status_classes = {
            'not_started': 'bg-secondary',
            'in_progress': 'bg-primary',
            'completed': 'bg-success',
            'abandoned': 'bg-danger'
        }
        return status_classes.get(self.status, 'bg-secondary')
    
    def duration(self):
        if not self.end_time or self.status not in ['completed', 'abandoned']:
            return None
        delta = self.end_time - self.start_time
        return round(delta.total_seconds() / 60, 1)
        
    def observation_count(self):
        return self.observations.filter(status='completed').count()
        
    def is_active(self):
        return self.status in ['not_started', 'in_progress']
        
    def get_progress_percentage(self):
        if not self.target_plants_surveyed or self.target_plants_surveyed <= 0:
            return 0
        completed = self.observation_count()
        percentage = (completed / self.target_plants_surveyed) * 100
        return min(max(int(percentage), 0), 100)
        
    def get_unique_pests(self):
        return Pest.objects.filter(observations__session=self, observations__status='completed').distinct()
        
    def get_unique_diseases(self):
        return Disease.objects.filter(observations__session=self, observations__status='completed').distinct()
        
    def summarize(self):
        return {
            'id': self.session_id,
            'farm_name': self.farm.name,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'status': self.status,
            'duration_minutes': self.duration(),
            'observations_count': self.observation_count(),
            'target_plants': self.target_plants_surveyed,
            'progress_percentage': self.get_progress_percentage(),
            'unique_pests_count': self.get_unique_pests().count(),
            'unique_diseases_count': self.get_unique_diseases().count(),
            'surveyor_name': f"{self.surveyor.first_name} {self.surveyor.last_name}".strip() or self.surveyor.username
        }

class ObservationManager(models.Manager):
    def completed(self):
        return self.filter(status='completed')
        
    def with_pests(self):
        return self.filter(pests_observed__isnull=False).distinct()
        
    def with_diseases(self):
        return self.filter(diseases_observed__isnull=False).distinct()
        
    def by_session(self, session_id):
        return self.filter(session__session_id=session_id)


class Observation(models.Model):
    session = models.ForeignKey(SurveySession, on_delete=models.CASCADE, related_name='observations', db_index=True)
    observation_time = models.DateTimeField(default=timezone.now, db_index=True)
    pests_observed = models.ManyToManyField(Pest, related_name='observations', blank=True)
    diseases_observed = models.ManyToManyField(Disease, related_name='observations', blank=True)
    notes = models.TextField(blank=True, null=True)
    plant_sequence_number = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=10, choices=OBSERVATION_STATUS_CHOICES, default='completed', db_index=True)
    
    objects = ObservationManager()

    class Meta:
        ordering = ['observation_time']
        verbose_name = "Observation Point"
        verbose_name_plural = "Observation Points"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['session', 'status']),
            models.Index(fields=['observation_time']),
            models.Index(fields=['plant_sequence_number']),
        ]
    
    def __str__(self):
        return f"Observation {self.plant_sequence_number or 'n/a'} on {self.observation_time.strftime('%Y-%m-%d %H:%M')}"
        
    def has_pests(self):
        return self.pests_observed.exists()
        
    def has_diseases(self):
        return self.diseases_observed.exists()
        
    def finalize(self, save=True):
        self.status = 'completed'
        if save:
            self.save()
        return self
        
    def to_dict(self):
        return {
            'id': self.id,
            'observation_time': self.observation_time,
            'plant_sequence_number': self.plant_sequence_number,
            'status': self.status,
            'notes': self.notes,
            'pests': list(self.pests_observed.values('id', 'name')),
            'diseases': list(self.diseases_observed.values('id', 'name')),
        }