# Custom decorators for this project

from functools import wraps

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied

from .models import Staff, StaffAdminRole


def staff_only(function):
    """
    Checks the logged in User is an internal member of staff with a valid related Staff object
    """
    def wrapper(request, *args, **kwargs):
        try:
            staff = Staff.objects.get(user=request.user)
            if staff.is_external:
                raise PermissionDenied("""Sorry, but this page is for internal staff only""")
        except Staff.DoesNotExist:
            # Is this a Superuser
            # TODO: Should no longer be necessary now Staff objects are auto created
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
    """
    Checks the logged in User is an External Examiner with a valid related Staff object
    """
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


def get_internal_staff(user):
    """The internal (not external) Staff object for a logged in user, or None"""
    if not user.is_authenticated:
        return None
    staff = Staff.objects.filter(user=user).first()
    if staff is None or staff.is_external:
        return None
    return staff


def has_admin_permission(user, permission):
    """Whether the user is a superuser, or internal staff holding an AdminRole granting the capability"""
    if user.is_authenticated and user.is_superuser:
        return True
    staff = get_internal_staff(user)
    return staff is not None and staff.has_admin_permission(permission)


def admin_permission_required(view_func=None, *, permission):
    """
    Restricts a view to superusers and internal staff holding an AdminRole that grants the
    named capability, e.g. @admin_permission_required(permission='can_manage_school_groups').
    Anyone else gets 403.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not has_admin_permission(request.user, permission):
                raise PermissionDenied("You do not have permission to access this page.")
            return view_func(request, *args, **kwargs)
        return wrapper

    if view_func is not None:
        return decorator(view_func)
    return decorator


class AdminPermissionRequiredMixin(UserPassesTestMixin):
    """Class-based view equivalent of admin_permission_required: set the permission attribute"""
    permission = None

    def test_func(self):
        if not self.permission:
            raise ImproperlyConfigured("AdminPermissionRequiredMixin requires the 'permission' attribute to be set.")
        return has_admin_permission(self.request.user, self.permission)

    def handle_no_permission(self):
        raise PermissionDenied("You do not have permission to access this page.")


def admin_area(function):
    """
    For the Admin menu: users with Django's staff status (is_staff) or superusers, as before,
    and also internal staff holding any AdminRole
    """
    @wraps(function)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if user.is_staff or user.is_superuser:
            return function(request, *args, **kwargs)
        staff = get_internal_staff(user)
        if staff is not None and StaffAdminRole.objects.filter(staff=staff).exists():
            return function(request, *args, **kwargs)
        raise PermissionDenied("You do not have admin permissions.")
    return wrapper

