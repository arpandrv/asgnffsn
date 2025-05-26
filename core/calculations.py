import math
from decimal import Decimal, ROUND_CEILING

# Constants
Z_SCORES = {
    90: Decimal('1.645'),
    95: Decimal('1.960'),
    99: Decimal('2.575'),
}
DEFAULT_CONFIDENCE = 95
DEFAULT_MARGIN_OF_ERROR = Decimal('0.05')

def calculate_surveillance_effort(farm, confidence_level_percent, prevalence_p):
    """
    Calculates the required sample size based on farm population (N),
    confidence level (z), expected prevalence (p), and margin of error (d).
    Uses the formula for finite populations.
    """
    if farm is None:
        return {'error': 'Farm object is required for calculation.', 
                'required_plants_to_survey': None, 'percentage_of_total': None, 'survey_frequency': None, 'N': None}

    N = farm.total_plants()
    if N is None or N <= 0:
        return {'error': 'Total number of plants (N) for the farm must be calculated and positive.', 
                'required_plants_to_survey': None, 'percentage_of_total': None, 'survey_frequency': None, 'N': N}

    try:
        confidence_level_int = int(confidence_level_percent)
    except (ValueError, TypeError):
        confidence_level_int = DEFAULT_CONFIDENCE

    z = Z_SCORES.get(confidence_level_int, Z_SCORES[DEFAULT_CONFIDENCE])
    
    try:
        p = Decimal(str(prevalence_p))
    except Exception:
         return {'error': 'Invalid prevalence value (p). Must be a number.', 
                 'required_plants_to_survey': None, 'percentage_of_total': None, 'survey_frequency': None, 'N': N}

    d = DEFAULT_MARGIN_OF_ERROR

    if not (Decimal(0) < p < Decimal(1)):
        if p == Decimal(0):
            required_plants = 0
        elif p >= Decimal(1):
            required_plants = N
        else:
            return {'error': 'Prevalence (p) must be between 0 and 1.',
                    'required_plants_to_survey': None, 'percentage_of_total': None, 'survey_frequency': None, 'N': N}

        if 'required_plants' in locals():
            percentage_of_total = Decimal('0.0')
            if N > 0 and required_plants > 0:
                percentage_of_total = round((Decimal(required_plants) / Decimal(N)) * 100, 1)
            
            survey_frequency = None
            if required_plants is not None and required_plants > 0:
                 survey_frequency = int(Decimal(N).quantize(Decimal('1'), rounding=ROUND_CEILING) / Decimal(required_plants).quantize(Decimal('1'), rounding=ROUND_CEILING))
            
            return {
                'N': N,
                'confidence_level_percent': confidence_level_percent,
                'prevalence_p': float(p),
                'margin_of_error': float(d),
                'required_plants_to_survey': required_plants,
                'percentage_of_total': float(percentage_of_total),
                'survey_frequency': survey_frequency,
                'error': None if p==Decimal(0) or p>=Decimal(1) else "Prevalence (p) out of expected range."
            }

    try:
        # Calculate m = (z^2 * p * (1-p)) / d^2
        m_numerator = (z**2) * p * (Decimal(1) - p)
        m_denominator = d**2
        if m_denominator == Decimal(0):
             raise ValueError("Margin of error squared cannot be zero.")
        m = m_numerator / m_denominator

        # Calculate n = m / (1 + ((m - 1) / N))
        N_decimal = Decimal(N)
        n_denominator_component = (m - Decimal(1)) / N_decimal
        n_denominator = Decimal(1) + n_denominator_component
        
        if n_denominator == Decimal(0):
             raise ValueError("Calculation resulted in division by zero for sample size.")
        
        n_float = m / n_denominator

        # Final sample size (rounded up, cannot exceed N)
        required_plants = min(N, math.ceil(float(n_float)))
        
        if N > 0 and required_plants < 1 and n_float > 0:
            required_plants = 1
        elif N == 0:
            required_plants = 0
            
        percentage_of_total = Decimal('0.0')
        if N > 0 and required_plants > 0:
            percentage_of_total = round((Decimal(required_plants) / N_decimal) * 100, 1)
        
        survey_frequency = None
        if required_plants is not None and required_plants > 0:
            survey_frequency = int(N // required_plants) if N >= required_plants else None
            if survey_frequency is not None and survey_frequency == 0 and N > 0:
                survey_frequency = 1

        return {
            'N': N,
            'confidence_level_percent': confidence_level_percent,
            'prevalence_p': float(p),
            'margin_of_error': float(d),
            'required_plants_to_survey': int(required_plants),
            'percentage_of_total': float(percentage_of_total),
            'survey_frequency': survey_frequency,
            'error': None
        }

    except ValueError as ve:
        print(f"ValueError in sample size calculation for farm {farm.id if farm else 'Unknown'}: {ve}")
        return {'error': f'Calculation error: {ve}. Please check input parameters.', 
                'required_plants_to_survey': None, 'percentage_of_total': None, 'survey_frequency': None, 'N': N}
    except Exception as e:
        print(f"Unexpected error in sample size calculation for farm {farm.id if farm else 'Unknown'}: {e}")
        return {'error': f'An unexpected calculation error occurred: {e}', 
                'required_plants_to_survey': None, 'percentage_of_total': None, 'survey_frequency': None, 'N': N}

__all__ = [
    'calculate_surveillance_effort',
    'Z_SCORES',
    'DEFAULT_CONFIDENCE',
    'DEFAULT_MARGIN_OF_ERROR'
]