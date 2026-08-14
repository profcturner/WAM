# services/formula_engine.py
import math
from simpleeval import simple_eval, InvalidExpression

ALLOWED_FUNCTIONS = {
    'log': math.log,
    'log2': math.log2,
    'log10': math.log10,
    'sqrt': math.sqrt,
    'abs': abs,
    'min': min,
    'max': max,
    'round': round,
}

class FormulaError(Exception):
    pass


def _evaluate(formula: str, variables: dict) -> float:
    """Core evaluation — not called directly by application code."""
    try:
        result = simple_eval(formula, names=variables, functions=ALLOWED_FUNCTIONS)
        return float(result)
    except InvalidExpression as e:
        raise FormulaError(f"Invalid formula '{formula}': {e}")
    except ZeroDivisionError:
        raise FormulaError(f"Division by zero in formula '{formula}'")


def calculate_contact_hours(package, credits: int, students: int) -> float:
    variables = {
        'credits': credits,
        'students': students,
        'contact_scaling': package.credit_contact_scaling,
    }
    if package.contact_formula:
        return _evaluate(package.contact_formula, variables)
    # Fallback to legacy scalar behaviour if no formula set
    return credits * package.credit_contact_scaling


def calculate_admin_hours(package, credits: int, students: int, contact: float) -> float:
    variables = {
        'credits': credits,
        'students': students,
        'contact': contact,
        'admin_scaling': package.contact_admin_scaling,
        'assessment_scaling': package.contact_assessment_scaling,
    }
    if package.admin_formula:
        return _evaluate(package.admin_formula, variables)
    return contact * package.contact_admin_scaling


def calculate_assessment_hours(package, credits: int, students: int,
                                contact: float, admin: float) -> float:
    variables = {
        'credits': credits,
        'students': students,
        'contact': contact,
        'admin': admin,
        'admin_scaling': package.contact_admin_scaling,
        'assessment_scaling': package.contact_assessment_scaling,
    }
    if package.assessment_formula:
        return _evaluate(package.assessment_formula, variables)
    return contact * package.contact_assessment_scaling


def calculate_all_hours(package, credits: int, students: int) -> dict:
    """Convenience method returning all three in one call."""
    contact = calculate_contact_hours(package, credits, students)
    admin = calculate_admin_hours(package, credits, students, contact)
    assessment = calculate_assessment_hours(package, credits, students, contact, admin)
    return {
        'contact': contact,
        'admin': admin,
        'assessment': assessment,
    }

def calculate_coordinator_hours(package, credits: int, students: int) -> float:
    if package.coordinator_formula:
        variables = {
            'credits': credits,
            'students': students,
        }
        return _evaluate(package.coordinator_formula, variables)
    # Fallback if no formula set — returns 0 rather than guessing
    return 0.0