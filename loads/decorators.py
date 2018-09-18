# Custom decorators for this project

from django.core.exceptions import PermissionDenied
from .models import Staff
from .models import ExternalExaminer

def staff_only(function):
    """Checks the logged in User has a valid related Staff object"""
    def wrapper(request, *args, **kwargs):
        staff = Staff.objects.get(user=request.user)

        if not staff:
            # We should redirect really, but for now
            raise PermissionDenied
        else:
            return function(request, *args, **kwargs)

    # Keep the name and doc values intact after wrapping
    wrapper.__doc__ = function.__doc__
    wrapper.__name__ = function.__name__
    return wrapper


def external_only(function):
    """Checks the logged in User has a valid related Staff object"""
    def wrapper(request, *args, **kwargs):
        external = ExternalExaminer.objects.get(user=request.user)

        if not external:
            # We should redirect really, but for now
            raise PermissionDenied
        else:
            return function(request, *args, **kwargs)

    # Keep the name and doc values intact after wrapping
    wrapper.__doc__ = function.__doc__
    wrapper.__name__ = function.__name__
    return wrapper


def admin_only(function):
    """Checks the logged in User has is_staff or is_superuser"""
    def wrapper(request, *args, **kwargs):
        if request.user.is_staff or request.user.is_superuser:
            return function(request, *args, **kwargs)
        else:
            # We should redirect really, but for now
            raise PermissionDenied

    # Keep the name and doc values intact after wrapping
    wrapper.__doc__ = function.__doc__
    wrapper.__name__ = function.__name__
    return wrapper


