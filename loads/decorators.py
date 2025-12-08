# Custom decorators for this project

from django.core.exceptions import PermissionDenied
from .models import Staff


def staff_only(function):
    """Checks the logged in User has a valid related Staff object"""
    def wrapper(request, *args, **kwargs):
        try:
            staff = Staff.objects.get(user=request.user)
        except Staff.DoesNotExist:
            # Is this a Superuser
            if request.user.is_superuser:
                # This is likely a created superuser with no matching Staff object. Create one.
                staff = Staff.objects.create(user=request.user, staff_number=request.user.get_username(), title="",
                                             package=None)
                # Ok, let them through now.
                return function(request, *args, **kwargs)
            else:
                # We should redirect really, but for now
                raise PermissionDenied("""Your user has no matching staff object.
                This is likely to be because no account has been created for you.""")
        else:
            return function(request, *args, **kwargs)

    # Keep the name and doc values intact after wrapping
    wrapper.__doc__ = function.__doc__
    wrapper.__name__ = function.__name__
    return wrapper


def external_only(function):
    """Checks the logged in User has a valid related Staff object"""
    def wrapper(request, *args, **kwargs):
        try:
            staff = Staff.objects.get(user=request.user)
            if not staff.is_external:
                raise PermissionDenied
        except Staff.DoesNotExist:
            # We should redirect really, but for now
            raise PermissionDenied("""Your user has no matching staff object.
            This is likely to be because no account has been created for you.""")
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
            raise PermissionDenied("You do not have admin permissions.")

    # Keep the name and doc values intact after wrapping
    wrapper.__doc__ = function.__doc__
    wrapper.__name__ = function.__name__
    return wrapper
