"""
Directory integration for WAM.

WAM can learn about staff from an institutional directory (for example Active
Directory / Entra ID), either at login through an external authentication
backend, or in bulk before anyone logs in ("onboarding").

WAM itself stays agnostic about any institution's directory layout. Everything
here works with a *staff record*: a plain dict using WAM's own vocabulary.

    username        (required) the Django username; must match what your
                    authentication backend uses, or a duplicate User will
                    be created at first login
    staff_number    the staff number (defaults to the username)
    first_name      \
    last_name        > copied to the Django User
    email           /
    job_title       the job title
    school          \
    faculty          > *system names* of the School / Faculty / Campus. These are
    campus          /  matched or, if WAM_AUTO_CREATE_* allow, created
    is_external     True for External Examiners / associates (default False)

Only the keys present in a record, with a value, are applied. A missing or None
value means "unknown", so a source that knows nothing about campuses, or a person
with no campus in the directory, will not wipe a campus already set in WAM. The
same goes for a School, Faculty or Campus name that matches nothing (and isn't
created, see WAM_AUTO_CREATE_*).

Institution specific code (an authentication backend, or a DirectorySource
subclass) translates its own attributes into a staff record, and calls
apply_staff_record() or onboard_staff_record(). The onboard_staff management
command uses the DirectorySource named by the WAM_DIRECTORY_SOURCE setting.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils.module_loading import import_string

from loads.models import Staff, Campus, Faculty, School

logger = logging.getLogger(__name__)

RECORD_FIELDS = (
    'username', 'staff_number', 'first_name', 'last_name', 'email',
    'job_title', 'school', 'faculty', 'campus', 'is_external',
)


def apply_staff_record(user, record):
    """
    Update a User, its Staff object and School groups from a staff record.

    :param user:    a saved Django User
    :param record:  a staff record dict, see the module docstring
    :return:        the Staff object, or None if the User has none
    """
    logger.debug("applying staff record %s to user %s", record, user)

    unknown = set(record) - set(RECORD_FIELDS)
    if unknown:
        logger.warning("ignoring unknown staff record fields %s", sorted(unknown))

    # User fields
    user_changed = False
    for field in ('first_name', 'last_name', 'email'):
        if record.get(field) is not None:
            setattr(user, field, record[field])
            user_changed = True
    if user_changed:
        user.save()

    # loads.signals creates a Staff object for every new User, so find it by the
    # one-to-one link rather than by staff number, which may not yet be set.
    try:
        staff = Staff.objects.get(user=user)
    except Staff.DoesNotExist:
        logger.warning("no Staff object for user %s, could not apply record", user)
        return None

    if record.get('staff_number'):
        staff.staff_number = record['staff_number']
    if record.get('job_title') is not None:
        staff.job_title = record['job_title']
    if record.get('is_external') is not None:
        staff.is_external = bool(record['is_external'])

    # Organisational structure, matched (or created if so configured) by system name.
    # A name that is missing, or matches nothing, leaves the existing value alone.
    faculty = Faculty.get_or_create(record.get('faculty'))
    if faculty:
        staff.faculty = faculty
    school = School.get_or_create(record.get('school'), staff.faculty)
    if school:
        staff.school = school
    campus = Campus.get_or_create(record.get('campus'))
    if campus:
        staff.campus = campus

    staff.save()
    logger.debug("updated staff %s: school=%s faculty=%s campus=%s external=%s",
                 staff, staff.school, staff.faculty, staff.campus, staff.is_external)

    # School groups (created if WAM_AUTO_CREATE_SCHOOL_GROUPS)
    if staff.school:
        group_staff, group_academics, group_admin, group_externals = staff.school.create_groups()
        group = group_externals if staff.is_external else group_staff
        if group:
            user.groups.add(group)
            logger.debug("added user %s to group %s", user, group)

    return staff


def find_user(username):
    """Return the User with this username (case insensitively), or None."""
    User = get_user_model()
    return User.objects.filter(**{f"{User.USERNAME_FIELD}__iexact": username}).first()


def onboard_staff_record(record):
    """
    Create (or update) the User and Staff described by a staff record.

    New Users get an unusable password, so they can only log in through
    external authentication.

    :param record:  a staff record dict, which must include 'username'
    :return:        a tuple of (Staff object, created)
    """
    username = record.get('username')
    if not username:
        raise ValueError("a staff record must include a username")

    User = get_user_model()
    with transaction.atomic():
        user = find_user(username)
        created = user is None
        if created:
            # Saving fires loads.signals.create_staff, which makes the Staff object
            user = User(**{User.USERNAME_FIELD: username})
            user.set_unusable_password()
            user.save()
            logger.info("onboarded new user %s", username)

        staff = apply_staff_record(user, record)

    return staff, created


class DirectorySource:
    """
    Base class for a source of staff records, used by the onboard_staff command.

    Subclass this, and name your class in the WAM_DIRECTORY_SOURCE setting as a
    dotted path, for example "myuni.directory.MyDirectorySource".
    """

    def staff_in_school(self, school):
        """
        Yield staff records for everyone who should be onboarded into a School.

        :param school:  the School, as the directory names it (its system name)
        """
        raise NotImplementedError


def get_directory_source():
    """Instantiate the DirectorySource named by the WAM_DIRECTORY_SOURCE setting."""
    path = getattr(settings, 'WAM_DIRECTORY_SOURCE', None)
    if not path:
        raise ImproperlyConfigured("WAM_DIRECTORY_SOURCE is not set")
    return import_string(path)()
