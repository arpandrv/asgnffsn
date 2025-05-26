from django.contrib import admin
from .models import (
    Grower, Farm, PlantType, PlantPart, Pest, Disease,
    Region, SurveillanceCalculation,
    SeasonalStage, SurveySession, Observation
)

@admin.register(Grower)
class GrowerAdmin(admin.ModelAdmin):
    list_display = ('user', 'farm_name', 'contact_number')
    search_fields = ('user__username', 'farm_name')

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'climate_zone', 'state_abbreviation')
    search_fields = ('name', 'state_abbreviation')

@admin.register(PlantType)
class PlantTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(PlantPart)
class PlantPartAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Pest)
class PestAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_affected_types', 'get_affected_parts')
    search_fields = ('name',)
    filter_horizontal = ('affects_plant_types', 'affects_plant_parts')

    @admin.display(
        description='Affects Plant Types'
    )
    def get_affected_types(self, obj):
        return ", ".join([p.name for p in obj.affects_plant_types.all()])

    @admin.display(
        description='Affects Plant Parts'
    )
    def get_affected_parts(self, obj):
        return ", ".join([p.name for p in obj.affects_plant_parts.all()])

@admin.register(Disease)
class DiseaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_affected_types', 'get_affected_parts')
    search_fields = ('name',)
    filter_horizontal = ('affects_plant_types', 'affects_plant_parts')

    @admin.display(
        description='Affects Plant Types'
    )
    def get_affected_types(self, obj):
        return ", ".join([p.name for p in obj.affects_plant_types.all()])

    @admin.display(
        description='Affects Plant Parts'
    )
    def get_affected_parts(self, obj):
        return ", ".join([p.name for p in obj.affects_plant_parts.all()])

@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'region', 'plant_type', 'size_hectares', 'stocking_rate', 'boundary_present')
    list_filter = ('region', 'plant_type')
    search_fields = ('name', 'owner__user__username', 'region__name', 'formatted_address')
    readonly_fields = ('boundary',)

    @admin.display(
        description='Boundary Saved',
        boolean=True,
    )
    def boundary_present(self, obj):
        return bool(obj.boundary)

@admin.register(SurveillanceCalculation)
class SurveillanceCalculationAdmin(admin.ModelAdmin):
    list_display = ('farm', 'date_created', 'created_by', 'season', 'confidence_level', 'required_plants', 'is_current')
    list_filter = ('farm__region', 'farm__plant_type', 'season', 'confidence_level', 'is_current')
    search_fields = ('farm__name', 'created_by__username', 'notes')
    readonly_fields = ('date_created',)
    date_hierarchy = 'date_created'
    ordering = ('-date_created',)

@admin.register(SeasonalStage)
class SeasonalStageAdmin(admin.ModelAdmin):
    list_display = ('name', 'months', 'prevalence_p')
    search_fields = ('name',)
    filter_horizontal = ('active_pests', 'active_diseases')

@admin.register(SurveySession)
class SurveySessionAdmin(admin.ModelAdmin):
    list_display = ('farm', 'surveyor', 'start_time', 'end_time', 'status', 'display_observation_count', 'session_id')
    list_filter = ('status', 'farm__region', 'surveyor')
    search_fields = ('farm__name', 'surveyor__username', 'session_id')
    readonly_fields = ('session_id', 'start_time', 'end_time', 'display_observation_count')
    date_hierarchy = 'start_time'

    @admin.display(
        description="Completed Observations"
    )
    def display_observation_count(self, obj):
        return obj.observation_count() 

@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = ('session', 'observation_time', 'plant_sequence_number', 'get_pest_count', 'get_disease_count')
    list_filter = ('session__farm', 'observation_time', 'status')
    search_fields = ('session__session_id', 'notes', 'plant_sequence_number')
    filter_horizontal = ('pests_observed', 'diseases_observed')
    readonly_fields = ('observation_time',)

    @admin.display(
        description='Pests'
    )
    def get_pest_count(self, obj):
        return obj.pests_observed.count()

    @admin.display(
        description='Diseases'
    )
    def get_disease_count(self, obj):
        return obj.diseases_observed.count()
