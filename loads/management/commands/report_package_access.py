"""
Help move managers from extra group memberships to oversight roles.

Lists:
  - work packages that aren't linked to any School, so no oversight role can reach them;
  - people who are members (through groups) of packages for more than one School. Some genuinely
    work in several Schools; others were only added to see them, and could be given an admin role
    with "Can view workloads" for those Schools instead, then removed from the extra groups. For
    each School, it says whether they have any workload there (module allocations or activities),
    which suggests which memberships are real.

It only reports; nothing is changed.
"""
from django.core.management.base import BaseCommand

from loads.models import Activity, ModuleStaff, Staff, WorkPackage


class Command(BaseCommand):
    help = "Report packages without Schools, and people who are members of more than one School's packages"

    def add_arguments(self, parser):
        parser.add_argument('--include-archived', action='store_true',
                            help="Include archived packages (left out by default)")

    def handle(self, *args, **options):
        packages = WorkPackage.objects.prefetch_related('schools', 'groups')
        if not options['include_archived']:
            packages = packages.filter(archive=False)

        orphans = [package for package in packages if not package.schools.exists()]
        self.stdout.write(self.style.MIGRATE_HEADING("Work packages with no School"))
        if orphans:
            for package in orphans:
                self.stdout.write(f"  {package} (id {package.pk})")
            self.stdout.write("  Set their Schools in Django admin, under Work packages, so oversight roles can reach them.")
        else:
            self.stdout.write("  None")

        # Each person's packages through their groups, and those packages' Schools
        schools_by_staff = {}
        for package in packages:
            schools = list(package.schools.all())
            if not schools:
                continue
            for staff in Staff.objects.filter(user__groups__in=package.groups.all(), is_external=False,
                                              user__is_active=True).distinct().select_related('user'):
                for school in schools:
                    schools_by_staff.setdefault(staff, {}).setdefault(school, []).append(package)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Members of more than one School's packages"))
        several = {staff: by_school for staff, by_school in schools_by_staff.items() if len(by_school) > 1}
        if not several:
            self.stdout.write("  None")
        for staff in sorted(several, key=lambda s: (s.user.last_name, s.user.first_name)):
            home = staff.school.name if staff.school else "no School set"
            roles = ", ".join(str(assignment.role) for assignment in staff.admin_roles.select_related('role'))
            self.stdout.write(f"  {staff} ({staff.user.username}; {home}){'; roles: ' + roles if roles else ''}")
            for school, school_packages in sorted(several[staff].items(), key=lambda item: item[0].name):
                workload = (ModuleStaff.objects.filter(staff=staff, package__in=school_packages).exists() or
                            Activity.objects.filter(staff=staff, package__in=school_packages).exists())
                note = "has workload" if workload else "no workload: perhaps oversight only"
                names = ", ".join(str(package) for package in school_packages)
                self.stdout.write(f"      {school.name}: {note} ({names})")
