# Context Processors make custom variables in all templates

from django.conf import settings

from loads.models import Staff
from WAM.settings import WAM_ADFS_AUTH


def staff(request):
    """
    A context processor to add the logged in member of staff
    """

    try:
        staff = Staff.objects.get(user=request.user)
        return {
            'logged_in_staff': staff,
            # Whether their current work package is one they only oversee, through an admin role
            'viewing_only': bool(staff.package_id and not staff.is_external
                                 and not staff.can_edit_package(staff.package)),
        }
    except Staff.DoesNotExist:
        # The matching Staff user doesn't exist
        return {
            'logged_in_staff': None
        }
    except TypeError:
        # We should redirect really, but for now
        return {

        }


def auth_adfs(request):
    """
    A context processor to expose if external authentication is enabled
    """

    external = getattr(settings, 'WAM_EXTERNAL_ADFS_AUTH', None)
    return {
        'wam_adfs_auth': WAM_ADFS_AUTH,
        # How External Examiners sign in
        'wam_external_adfs_auth': WAM_ADFS_AUTH if external is None else external,
    }
