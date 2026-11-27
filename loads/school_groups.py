"""
Which staff and groups a local admin may manage on the School groups page.

Local admins (an AdminRole with can_manage_school_groups) can add internal staff to groups, and
remove them, for the Schools they're responsible for: those of their own work packages, and those
their role assignment covers (its Schools, Faculties, or all Schools; see StaffAdminRole). Groups
carry no permissions of their own, and are either:
  - marked "Local admins may manage membership" (GroupSettings.locally_managed) and attached to one
    of the admin's packages, or one of the chosen School's packages (WorkPackage.schools), or
  - the chosen School's own "Academic Staff" and "Admin Staff" groups (see School.create_groups),
    found by name, for a School the admin is responsible for.

The page shows one School's staff at a time, or optionally everyone in the admin's packages.
Superusers are responsible for every School. For the chosen School they see every group (without
permissions) in its packages, locally managed or not, such as its main Staff group; and they may
also choose to see every group without permissions, in any package or none.

The same scope decides what is shown and what may be changed when the page is saved.
"""
from django.contrib.auth.models import Group, User
from django.db.models import Q

from .models import School, Staff, WorkPackage


def school_subgroup_names(schools):
    """The names School.create_groups gives Schools' Academic and Admin Staff groups"""
    return [f"{school.name} {suffix}" for school in schools for suffix in ("Academic Staff", "Admin Staff")]


class SchoolGroupScope:
    """The staff (rows) and groups (columns) a user may manage, for the chosen options"""

    def __init__(self, user, school_id=None, widen=False, all_groups=False):
        self.user = user
        self.is_superuser = user.is_superuser
        self.viewer = Staff.objects.filter(user=user).first()
        self.widen = bool(widen)
        self.all_groups = bool(all_groups) and self.is_superuser

        # The Schools they're responsible for: all for superusers; otherwise those of their packages, and
        # those their School groups role covers
        if self.is_superuser:
            self.packages = WorkPackage.objects.all()
            self.responsible_schools = School.objects.all()
        elif self.viewer is not None and not self.viewer.is_external:
            member_packages = self.viewer.get_all_packages(include_hidden=True)
            covered = self._covered_schools()
            self.responsible_schools = School.objects.filter(
                Q(workpackages__in=member_packages) | Q(pk__in=covered)).distinct()
            self.packages = WorkPackage.objects.filter(
                Q(pk__in=member_packages) | Q(schools__in=covered)).distinct()
        else:
            self.packages = WorkPackage.objects.none()
            self.responsible_schools = School.objects.none()

        # Internal, active staff in any of the packages, or of a School they're responsible for
        # (External Examiners are never listed)
        self.package_staff = Staff.objects.filter(
            Q(user__groups__workpackage__in=self.packages) | Q(school__in=self.responsible_schools),
            is_external=False, user__is_active=True).distinct()

        self.schools = School.objects.filter(
            Q(staff__in=self.package_staff) | Q(pk__in=self.responsible_schools)).distinct().order_by('name')
        self.school = self._choose_school(school_id)

        people = self.package_staff
        if not self.widen:
            people = people.filter(school=self.school) if self.school else people.none()
        self.people = people.select_related('user').order_by('user__last_name', 'user__first_name')

        self.groups = self._find_groups()

    def _covered_schools(self):
        """The Schools the viewer's School groups role assignments cover"""
        assignments = self.viewer.admin_roles.filter(role__can_manage_school_groups=True)
        if assignments.filter(all_schools=True).exists():
            return School.objects.all()
        return School.objects.filter(Q(staffadminrole__in=assignments) |
                                     Q(faculty__staffadminrole__in=assignments)).distinct()

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
        found = Q(wam_settings__locally_managed=True, workpackage__in=packages)

        # The School (or Schools) shown, where they're responsible for it: its packages' locally managed
        # groups, and its own Academic and Admin Staff groups, whatever packages they're in
        shown = self.schools if self.widen else ([self.school] if self.school else [])
        shown = [school for school in shown if self.responsible_schools.filter(pk=school.pk).exists()]
        if shown:
            if self.is_superuser:
                # Superusers see every group in the School's packages (but not those with permissions)
                found |= Q(workpackage__schools__in=shown)
            else:
                found |= Q(wam_settings__locally_managed=True, workpackage__schools__in=shown)
            found |= Q(name__in=school_subgroup_names(shown))
        return groups.filter(found).distinct().order_by('name')

    @property
    def missing_subgroups(self):
        """The chosen School's Academic and Admin Staff groups that don't exist yet (superusers may create them)"""
        if not self.school or self.widen:
            return []
        names = school_subgroup_names([self.school])
        existing = set(Group.objects.filter(name__in=names).values_list('name', flat=True))
        return [name for name in names if name not in existing]

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
