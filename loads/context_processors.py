from django.contrib.auth.models import User

from loads.models import Staff

def staff(request):
    """A context processor to add the logged in member of staff"""

    try:
        staff = Staff.objects.get(user=request.user)
        return {
            'logged_in_staff': staff
        }
    except TypeError:
        # We should redirect really, but for now
        return {

        }
