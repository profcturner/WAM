

from loads.models import Staff


def staff(request):
    """A context processor to add the logged in member of staff"""

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
