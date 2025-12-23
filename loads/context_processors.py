# Context Processors make custom variables in all templates

from loads.models import Staff
from WAM.settings import WAM_ADFS_AUTH


def staff(request):
    """
    A context processor to add the logged in member of staff
    """

    try:
        staff = Staff.objects.get(user=request.user)
        return {
            'logged_in_staff': staff
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

    return {
        'wam_adfs_auth': WAM_ADFS_AUTH
    }
