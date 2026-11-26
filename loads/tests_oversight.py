"""
Tests for overseeing other Schools' work packages through an admin role ("Can view workloads"),
rather than by joining their groups.
"""
import io
import logging

from django.apps import apps
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import AdminRole, Faculty, School, StaffAdminRole, WorkPackage
from .testing import allocate, make_group, make_module, make_package, make_staff

PERMISSIONS = ['loads.add_module', 'loads.change_module', 'loads.add_modulestaff', 'loads.change_modulestaff',
               'loads.delete_modulestaff', 'loads.add_activity', 'loads.add_programme',
               'loads.add_activitygenerator']


class OversightTestCase(TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.faculty = Faculty.objects.create(name="Faculty of Life and Health Sciences")
        self.other_faculty = Faculty.objects.create(name="Faculty of Computing")
        self.biomed = School.objects.create(name="School of Biomedical Sciences", faculty=self.faculty)
        self.nursing = School.objects.create(name="School of Nursing", faculty=self.faculty)
        self.computing = School.objects.create(name="School of Computing", faculty=self.other_faculty)

        def package(school, name, **kwargs):
            group = make_group(f"{school.name} Staff")
            created = make_package(name, group=group, **kwargs)
            created.schools.add(school)
            return created, group

        self.biomed_package, self.biomed_group = package(self.biomed, "Biomed 2026/27")
        self.nursing_package, self.nursing_group = package(self.nursing, "Nursing 2026/27", hidden=True)
        self.computing_package, self.computing_group = package(self.computing, "Computing 2026/27")

        # A Head of School in Biomed, with the usual permissions there, overseeing Nursing too
        self.head = make_staff('head', group=self.biomed_group, package=self.nursing_package,
                               permissions=PERMISSIONS)
        self.lecturer = make_staff('nurse', group=self.nursing_group, package=self.nursing_package)
        self.module = make_module(self.nursing_package, code="NUR101")
        allocate(self.lecturer, self.module)

        self.viewer = AdminRole.objects.create(name="Workload viewer", can_view_workloads=True)
        self.assignment = StaffAdminRole.objects.create(staff=self.head, role=self.viewer)
        self.assignment.schools.add(self.nursing)


class AccessTests(OversightTestCase):

    def test_overseen_packages(self):
        self.assertEqual(list(self.head.get_overseen_packages()), [self.nursing_package])  # hidden, but included
        self.assertEqual(set(self.head.get_visible_packages()), {self.biomed_package, self.nursing_package})
        # Membership is unchanged, so nothing that edits sees the overseen package
        self.assertEqual(list(self.head.get_all_packages(include_hidden=True)), [self.biomed_package])
        self.assertTrue(self.head.can_edit_package(self.biomed_package))
        self.assertFalse(self.head.can_edit_package(self.nursing_package))

    def test_overseers_are_not_in_the_packages_staff(self):
        self.assertNotIn(self.head, self.nursing_package.get_all_staff())
        self.assertIn(self.lecturer, self.nursing_package.get_all_staff())

    def test_faculty_scope(self):
        self.assignment.schools.clear()
        self.assignment.faculties.add(self.faculty)
        self.assertEqual(set(self.head.get_overseen_packages()), {self.biomed_package, self.nursing_package})

    def test_all_schools(self):
        self.assignment.schools.clear()
        self.assignment.all_schools = True
        self.assignment.save()
        self.assertEqual(self.head.get_overseen_packages().count(), WorkPackage.objects.count())

    def test_role_without_the_capability(self):
        self.viewer.can_view_workloads = False
        self.viewer.save()
        self.assertFalse(self.head.get_overseen_packages().exists())

    def test_packages_without_schools_cant_be_overseen(self):
        self.nursing_package.schools.clear()
        self.assertFalse(self.head.get_overseen_packages().exists())

    def test_external_examiners_never_oversee(self):
        examiner = make_staff('examiner', is_external=True)
        StaffAdminRole.objects.create(staff=examiner, role=self.viewer, all_schools=True)
        self.assertFalse(examiner.get_overseen_packages().exists())

    def test_superusers(self):
        superuser = make_staff('super', superuser=True)
        self.assertTrue(superuser.can_edit_package(self.nursing_package))
        self.assertTrue(superuser.can_edit_package(None))


class ViewingTests(OversightTestCase):

    def get(self, name, *args, staff=None, **kwargs):
        self.client.force_login((staff or self.head).user)
        return self.client.get(reverse(name, args=args, kwargs=kwargs))

    def test_read_only_pages_open(self):
        for name, kwargs in (('loads', {}), ('loads_charts', {}), ('loads_modules', {'semesters': ''}),
                             ('modules_index', {'semesters': ''}), ('programmes_index', {}),
                             ('activities_index', {})):
            response = self.get(name, **kwargs)
            self.assertEqual(response.status_code, 200, name)
        self.assertEqual(self.get('modules_details', self.module.pk).status_code, 200)

    def test_read_only_notice(self):
        self.assertContains(self.get('loads'), "read-only")
        self.head.package = self.biomed_package
        self.head.save()
        self.assertNotContains(self.get('loads'), "read-only")
        self.nursing_package.hidden = False  # (members without staff status can't see hidden packages)
        self.nursing_package.save()
        self.assertNotContains(self.get('loads', staff=self.lecturer), "read-only")

    def test_can_choose_an_overseen_package(self):
        self.head.package = self.biomed_package
        self.head.save()
        self.client.force_login(self.head.user)
        response = self.client.get(reverse('workpackage_change'))
        self.assertIn(self.nursing_package, response.context['form'].fields['package'].queryset)
        self.client.post(reverse('workpackage_change'), {'package': self.nursing_package.pk})
        self.head.refresh_from_db()
        self.assertEqual(self.head.package, self.nursing_package)
        self.assertNotIn(self.computing_package, response.context['form'].fields['package'].queryset)

    def test_without_the_role_other_schools_stay_closed(self):
        self.assignment.delete()
        self.assertRedirects(self.get('loads'), reverse('workpackage_change'), fetch_redirect_response=False)
        self.assertNotEqual(self.get('modules_details', self.module.pk).status_code, 200)

    def test_module_page_has_no_edit_links(self):
        response = self.get('modules_details', self.module.pk)
        self.assertFalse(response.context['can_edit'])
        self.assertNotContains(response, reverse('module_staff_allocation', args=[self.nursing_package.pk,
                                                                                  self.module.pk]))
        self.assertNotContains(response, reverse('update module', args=[self.module.pk]))
        self.assertNotContains(response, reverse('add_assessment_resource', args=[self.module.pk]))


class NoEditingTests(OversightTestCase):
    """Overseeing a package never lets someone change it, whatever Django permissions they hold"""

    def assertForbidden(self, response, label):
        self.assertTrue(response.status_code in (302, 403, 404), label)
        if response.status_code == 302:
            self.assertEqual(response.url, reverse('forbidden'), label)

    def test_create_pages_in_the_current_package(self):
        self.client.force_login(self.head.user)
        for name in ('create module', 'create activity', 'create programme', 'create generator', 'create task'):
            self.assertForbidden(self.client.get(reverse(name)), name)
            self.assertForbidden(self.client.post(reverse(name), {'name': 'x'}), name)

    def test_create_pages_still_work_in_their_own_package(self):
        self.head.package = self.biomed_package
        self.head.save()
        self.client.force_login(self.head.user)
        self.assertEqual(self.client.get(reverse('create module')).status_code, 200)

    def test_editing_the_overseen_module(self):
        self.client.force_login(self.head.user)
        self.assertForbidden(self.client.get(reverse('module_staff_allocation',
                                                     args=[self.nursing_package.pk, self.module.pk])), 'allocations')
        self.assertForbidden(self.client.get(reverse('update module', args=[self.module.pk])), 'update')
        self.assertForbidden(self.client.get(reverse('module_hours_by_person', args=[self.module.pk])), 'hours')
        self.assertForbidden(self.client.get(reverse('module_hours_import')), 'import')


class SetUpTests(OversightTestCase):

    def test_migration_links_packages_to_schools_by_main_group(self):
        from importlib import import_module
        migration = import_module('loads.migrations.0061_oversight_roles')
        for package in WorkPackage.objects.all():
            package.schools.clear()
        extra = make_package("Shared 2026/27", group=self.biomed_group)
        extra.groups.add(self.computing_group, make_group("Somebody's Own Group"))
        migration.link_packages_to_schools(apps, None)
        self.assertEqual(list(self.biomed_package.schools.all()), [self.biomed])
        self.assertEqual(set(extra.schools.all()), {self.biomed, self.computing})

    def test_report(self):
        manager = make_staff('manager', group=self.biomed_group)
        manager.user.groups.add(self.computing_group)
        allocate(manager, make_module(self.biomed_package, code="BMS101"))
        make_package("Orphan 2026/27")
        out = io.StringIO()
        call_command('report_package_access', stdout=out)
        report = out.getvalue()
        self.assertIn("Orphan 2026/27", report)
        self.assertIn("manager", report)
        self.assertIn("School of Biomedical Sciences: has workload", report)
        self.assertIn("School of Computing: no workload", report)
        self.assertNotIn("nurse", report)
