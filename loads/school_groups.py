"""
Which staff and groups a local admin may manage on the School groups page.

Local admins (an AdminRole with can_manage_school_groups) can add internal staff in their own
work packages to groups, and remove them, where each group:
  - is attached to one of the admin's work packages (hidden packages included),
  - is marked "Local admins may manage membership" (GroupSettings.locally_managed), and
  - carries no permissions of its own.

The page shows one School's staff at a time, or optionally everyone in the admin's packages.
Superusers' packages are all packages, and they may also choose to see every group without
permissions, whether or not it's marked as locally managed.

The same scope decides what is shown and what may be changed when the page is saved.
"""
from django.contrib.auth.models import Group, User

from .models import School, Staff, WorkPackage


class SchoolGroupScope:
    """The staff (rows) and groups (columns) a user may manage, for the chosen options"""

    def __init__(self, user, school_id=None, widen=False, all_groups=False):
        self.user = user
        self.is_superuser = user.is_superuser
        self.viewer = Staff.objects.filter(user=user).first()
        self.widen = bool(widen)
        self.all_groups = bool(all_groups) and self.is_superuser

        if self.is_superuser:
            self.packages = WorkPackage.objects.all()
        elif self.viewer is not None:
            self.packages = self.viewer.get_all_packages(include_hidden=True)
        else:
            self.packages = WorkPackage.objects.none()

        # Internal, active staff in any of the packages (External Examiners are never listed)
        self.package_staff = Staff.objects.filter(
            user__groups__workpackage__in=self.packages, is_external=False, user__is_active=True).distinct()

        self.schools = School.objects.filter(staff__in=self.package_staff).distinct().order_by('name')
        self.school = self._choose_school(school_id)

        people = self.package_staff
        if not self.widen:
            people = people.filter(school=self.school) if self.school else people.none()
        self.people = people.select_related('user').order_by('user__last_name', 'user__first_name')

        self.groups = self._find_groups()

    def _choose_school(self, school_id):
        if school_id:
            chosen = self.schools.filter(pk=school_id).first()
            if chosen:
                return chosen
        if self.viewer is not None and self.viewer.school_id:
            own = self.schools.filter(pk=self.viewer.school_id).first()
            if own:
                return own
        return self.schools.first()

    def _find_groups(self):
        groups = Group.objects.filter(permissions__isnull=True)
        if self.all_groups:
            return groups.distinct().order_by('name')
        if self.is_superuser:
            # Superusers are in no particular packages: use those the listed people belong to
            packages = WorkPackage.objects.filter(groups__user__staff__in=self.people)
        else:
            packages = self.packages
        return groups.filter(wam_settings__locally_managed=True,
                             workpackage__in=packages).distinct().order_by('name')

    def membership(self):
        """The (staff pk, group pk) pairs in scope where the person is currently in the group"""
        user_to_staff = {staff.user_id: staff.pk for staff in self.people}
        pairs = User.groups.through.objects.filter(user_id__in=user_to_staff.keys(), group__in=self.groups)
        return {(user_to_staff[pair.user_id], pair.group_id) for pair in pairs}

    def allowed_pairs(self):
        """Every (staff pk, group pk) pair this user may change"""
        group_pks = list(self.groups.values_list('pk', flat=True))
        return {(staff.pk, group_pk) for staff in self.people for group_pk in group_pks}

    def short_name(self, group):
        """A group's name without the School's name in front, when showing one School"""
        if self.school and not self.widen and group.name.startswith(self.school.name + ' '):
            return group.name[len(self.school.name) + 1:]
        return group.name
