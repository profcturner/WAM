# validators.py
from simpleeval import simple_eval, InvalidExpression
from django.core.exceptions import ValidationError
import math

# The maximum variable set any formula could ever see
# Use representative dummy values for validation purposes
FORMULA_DUMMY_CONTEXT = {
    'credits': 20,
    'students': 100,
    'contact': 40.0,
    'admin': 10.0,
    'contact_scaling': 2.5,
    'admin_scaling': 1.0,
    'assessment_scaling': 1.0,
}

# A list of permitted formula functions
FORMULA_FUNCTIONS = {
    'log': math.log,
    'log2': math.log2,
    'log10': math.log10,
    'sqrt': math.sqrt,
    'abs': abs,
    'min': min,
    'max': max,
    'round': round,
}

def validate_formula(value):
    """Validate that a formula string is safe and evaluable."""
    if not value:
        return
    try:
        result = simple_eval(
            value,
            names=FORMULA_DUMMY_CONTEXT,
            functions=FORMULA_FUNCTIONS,
        )
        if not isinstance(result, (int, float)):
            raise ValidationError("Formula must evaluate to a number.")
    except InvalidExpression as e:
        raise ValidationError(f"Invalid formula: {e}")
    except ZeroDivisionError:
        pass  # acceptable — dummy values may trigger this; real data might not
    except Exception as e:
        raise ValidationError(f"Formula error: {e}")