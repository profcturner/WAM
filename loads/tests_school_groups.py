"""Tests for admin roles and the School groups page"""
import logging

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from .decorators import has_admin_permission
from .models import AdminRole, GroupSettings, School, StaffAdminRole
from .school_groups import SchoolGroupScope
from .testing import make_package, make_staff


def make_group(name, managed=False, permission=None):
    group = Group.objects.create(name=name)
    if managed:
        GroupSettings.objects.create(group=group, locally_managed=True)
    if permission:
        group.permissions.add(Permission.objects.get(codename=permission))
    return group


class SchoolGroupsTestCase(TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.biomed = School.objects.create(name="School of Biomedical Sciences")
        self.computing = School.objects.create(name="School of Computing")

        # Biomedical Sciences: the main group, two subgroups, examiners, and a group with permissions
        self.main = make_group("School of Biomedical Sciences Staff")
        self.academic = make_group("School of Biomedical Sciences Academic Staff", managed=True)
        self.admin_staff = make_group("School of Biomedical Sciences Admin Staff", managed=True)
        self.examiners = make_group("School of Biomedical Sciences External Examiners")
        self.powerful = make_group("Biomed Power Users", managed=True, permission='delete_staff')
        self.unattached = make_group("Biomed Unattached", managed=True)
        self.package = make_package("Biomed 2026/27")
        self.package.groups.add(self.main, self.academic, self.admin_staff, self.examiners, self.powerful)

        # Computing, in another package
        self.computing_main = make_group("School of Computing Staff")
        self.computing_academic = make_group("School of Computing Academic Staff", managed=True)
        self.computing_package = make_package("Computing 2026/27")
        self.computing_package.groups.add(self.computing_main, self.computing_academic)

        def person(username, group, school, **kwargs):
            staff = make_staff(username, group=group, first_name=username.title(), last_name="Person", **kwargs)
            staff.school = school
            staff.save()
            return staff

        self.local_admin = person('localadmin', self.main, self.biomed)
        self.lecturer = person('lecturer', self.main, self.biomed)
        self.secretary = person('secretary', self.main, self.biomed)
        self.joint = person('joint', self.main, self.computing)  # in the Biomed package, but a Computing School member
        self.computing_lecturer = person('complecturer', self.computing_main, self.computing)
        self.examiner = person('examiner', self.examiners, self.biomed, is_external=True)
        self.superuser = person('super', None, None, superuser=True)
        self.nobody = person('nobody', self.main, self.biomed)

        self.role = AdminRole.objects.create(name="School administrator", can_manage_school_groups=True)
        StaffAdminRole.objects.create(staff=self.local_admin, role=self.role)

    def scope(self, user=None, **kwargs):
        return SchoolGroupScope((user or self.local_admin.user), **kwargs)

    def page(self, staff, **params):
        self.client.force_login(staff.user)
        return self.client.get(reverse('school_groups'), params)

    def save(self, staff, ticks, **params):
        self.client.force_login(staff.user)
        url = reverse('school_groups')
        if params:
            url += '?' + '&'.join(f'{k}={v}' for k, v in params.items())
        return self.client.post(url, {f'm-{s.pk}-{g.pk}': 'on' for s, g in ticks})


class AdminRoleTests(SchoolGroupsTestCase):

    def test_role_grants_capability(self):
        self.assertTrue(self.local_admin.has_admin_permission('can_manage_school_groups'))
        self.assertFalse(self.lecturer.has_admin_permission('can_manage_school_groups'))
        self.assertTrue(self.superuser.has_admin_permission('can_manage_school_groups'))

    def test_role_without_the_capability(self):
        reader = AdminRole.objects.create(name="Reader")
        StaffAdminRole.objects.create(staff=self.lecturer, role=reader)
        self.assertFalse(has_admin_permission(self.lecturer.user, 'can_manage_school_groups'))

    def test_external_examiners_never_have_admin_permissions(self):
        StaffAdminRole.objects.create(staff=self.examiner, role=self.role)
        self.assertFalse(has_admin_permission(self.examiner.user, 'can_manage_school_groups'))

    def test_admin_menu_open_to_role_holders_without_staff_status(self):
        self.assertFalse(self.local_admin.user.is_staff)
        self.client.force_login(self.local_admin.user)
        response = self.client.get(reverse('custom_admin_index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('school_groups'))
        self.assertNotContains(response, reverse('create staff user'))  # still for staff-status users

    def test_admin_menu_closed_to_others(self):
        self.client.force_login(self.lecturer.user)
        self.assertEqual(self.client.get(reverse('custom_admin_index')).status_code, 403)


class SchoolGroupScopeTests(SchoolGroupsTestCase):

    def test_only_manageable_groups_in_the_admins_packages(self):
        """Not the main group, examiners, groups with permissions, unattached groups, or other packages'"""
        self.assertEqual(list(self.scope().groups), [self.academic, self.admin_staff])

    def test_one_schools_internal_staff(self):
        self.assertEqual(self.scope().school, self.biomed)
        self.assertCountEqual(self.scope().people, [self.local_admin, self.lecturer, self.secretary, self.nobody])

    def test_widen_to_everyone_in_my_packages(self):
        """Still within the admin's packages, and never External Examiners"""
        self.assertCountEqual(self.scope(widen=True).people,
                              [self.local_admin, self.lecturer, self.secretary, self.nobody, self.joint])

    def test_schools_offered_are_those_in_my_packages(self):
        self.assertEqual(list(self.scope().schools), [self.biomed, self.computing])  # joint is Computing
        scope = self.scope(school_id=self.computing.pk)
        self.assertEqual(list(scope.people), [self.joint])  # not the Computing package's staff

    def test_inactive_users_are_left_out(self):
        self.secretary.user.is_active = False
        self.secretary.user.save()
        self.assertNotIn(self.secretary, self.scope().people)

    def test_superuser_defaults_and_show_all(self):
        scope = self.scope(self.superuser.user, school_id=self.computing.pk)
        self.assertEqual(list(scope.groups), [self.academic, self.admin_staff, self.computing_academic])
        everything = self.scope(self.superuser.user, school_id=self.computing.pk, all_groups=True)
        self.assertIn(self.computing_main, everything.groups)
        self.assertIn(self.unattached, everything.groups)
        self.assertNotIn(self.powerful, everything.groups)  # groups with permissions: Django admin only

    def test_show_all_is_superusers_only(self):
        self.assertEqual(list(self.scope(all_groups=True).groups), [self.academic, self.admin_staff])

    def test_short_names(self):
        scope = self.scope()
        self.assertEqual(scope.short_name(self.academic), "Academic Staff")
        self.assertEqual(self.scope(widen=True).short_name(self.academic), self.academic.name)


class SchoolGroupsPageTests(SchoolGroupsTestCase):

    def test_who_can_open_the_page(self):
        self.assertEqual(self.page(self.local_admin).status_code, 200)
        self.assertEqual(self.page(self.superuser).status_code, 200)
        for staff in (self.lecturer, self.examiner):
            self.assertEqual(self.page(staff).status_code, 403, staff)

    def test_grid(self):
        self.lecturer.user.groups.add(self.academic)
        response = self.page(self.local_admin)
        self.assertEqual([label for group, label in response.context['columns']], ["Academic Staff", "Admin Staff"])
        self.assertContains(response, f'name="m-{self.lecturer.pk}-{self.academic.pk}"')
        cells = dict(response.context['rows'])[self.lecturer]
        self.assertEqual([member for group, member in cells], [True, False])

    def test_save_adds_and_removes(self):
        self.lecturer.user.groups.add(self.academic)
        self.save(self.local_admin, [(self.secretary, self.admin_staff), (self.nobody, self.academic)])
        self.assertFalse(self.lecturer.user.groups.filter(pk=self.academic.pk).exists())
        self.assertTrue(self.secretary.user.groups.filter(pk=self.admin_staff.pk).exists())
        self.assertTrue(self.nobody.user.groups.filter(pk=self.academic.pk).exists())
        # The main group is untouched, though it isn't on the form
        for staff in (self.lecturer, self.secretary, self.nobody):
            self.assertTrue(staff.user.groups.filter(pk=self.main.pk).exists(), staff)

    def test_changes_are_recorded(self):
        self.save(self.local_admin, [(self.secretary, self.admin_staff)])
        entry = LogEntry.objects.get()
        self.assertEqual((entry.user, entry.object_id), (self.local_admin.user, str(self.secretary.user.pk)))
        self.assertIn(self.admin_staff.name, entry.change_message)

    def test_tampered_form_cannot_reach_outside_the_scope(self):
        self.save(self.local_admin, [
            (self.lecturer, self.powerful),             # a group with permissions
            (self.lecturer, self.computing_academic),   # another package's group
            (self.lecturer, self.unattached),           # a group in no package
            (self.computing_lecturer, self.academic),   # someone outside the admin's packages
            (self.examiner, self.academic),             # an External Examiner
        ])
        self.assertFalse(self.lecturer.user.groups.exclude(pk=self.main.pk).exists())
        self.assertFalse(self.computing_lecturer.user.groups.filter(pk=self.academic.pk).exists())
        self.assertFalse(self.examiner.user.groups.filter(pk=self.academic.pk).exists())
        self.assertFalse(LogEntry.objects.exists())

    def test_saving_one_school_leaves_others_alone(self):
        """People not on the page keep their memberships"""
        self.joint.user.groups.add(self.academic)
        self.save(self.local_admin, [])  # Biomed page, nothing ticked
        self.assertTrue(self.joint.user.groups.filter(pk=self.academic.pk).exists())

    def test_widened_page_saves_everyone_shown(self):
        self.save(self.local_admin, [(self.joint, self.academic)], widen=1)
        self.assertTrue(self.joint.user.groups.filter(pk=self.academic.pk).exists())


class GroupSettingsTests(TestCase):

    def test_new_school_subgroups_are_locally_managed(self):
        school = School.objects.create(name="School of Nursing")
        staff, academics, admin, externals = school.create_groups()
        self.assertTrue(academics.wam_settings.locally_managed)
        self.assertTrue(admin.wam_settings.locally_managed)
        self.assertFalse(GroupSettings.objects.filter(group__in=[staff, externals]).exists())
