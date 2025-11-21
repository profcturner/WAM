# signals.py
import re

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Staff


@receiver(post_save, sender=User)
def create_staff(sender, instance, created, **kwargs):
    """
    :param sender: The class sending the signal
    :param instance: The User object that is triggering the signal
    :param created:
    :param kwargs:
    :return:

    Create a new Staff object automatically when a User object is created.

    If WAM_EXTERNAL_REGEX is set, it will use this to create a new External Examiner.
    If WAM_STAFF_REGEX is set, it will use this to create this as an internal member of staff.
    If either is set, and no REGEX is matched, the login should be disabled.
    """

    if created:
        # A special case is the superuser creation. Make a matching staff account.
        if instance.is_superuser:
            Staff.objects.create(user=instance, staff_number=instance.username, is_external=False,
                                 has_workload=False)
            return

        # So they are not a superuser, let's do some tests if regexs are configured
        if settings.WAM_STAFF_REGEX and settings.WAM_EXTERNAL_REGEX:
            # Best situation, everything is configured
            if re.fullmatch(settings.WAM_STAFF_REGEX, instance.username):
                Staff.objects.create(user=instance, staff_number=instance.username, is_external=False,
                                     has_workload=True)
                return

            if re.fullmatch(settings.WAM_EXTERNAL_REGEX, instance.username):
                Staff.objects.create(user=instance, staff_number=instance.username, is_external=True,
                                     has_workload=False)
                return

            # Disable login on no matches
            Staff.objects.create(user=instance, staff_number=instance.username, is_external=False,
                                 has_workload=True)
            instance.is_active = False
            instance.save()
            return

        # Or if a regex exists for staff and not externals... create staff on match, external otherwise
        if settings.WAM_STAFF_REGEX and not settings.WAM_EXTERNAL_REGEX:
            if re.fullmatch(settings.WAM_STAFF_REGEX, instance.username):
                Staff.objects.create(user=instance, staff_number=instance.username, is_external=False,
                                     has_workload=True)
                return
            else:
                Staff.objects.create(user=instance, staff_number=instance.username, is_external=True, has_workload = False)
                return

        # Or if a regex exists for external and not staff... create externals on match, staff otherwise
        if settings.WAM_EXTERNAL_REGEX and not settings.WAM_STAFF_REGEX:
            if re.fullmatch(settings.WAM_EXTERNAL_REGEX, instance.username):
                Staff.objects.create(user=instance, staff_number=instance.username, is_external=True,
                                     has_workload=False)
                return
            else:
                Staff.objects.create(user=instance, staff_number=instance.username, is_external=False, has_workload = True)
                return

        # Finally, if we are here, there are no regexs, try and make a generic staff object
        Staff.objects.create(user=instance, staff_number=instance.username)
        return
