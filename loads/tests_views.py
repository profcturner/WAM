"""
Behavioural tests for views: who may do what, and that the actions do what they say.

tests_clients.py checks pages open; these check permissions and side effects.
"""
import datetime
import logging
import shutil
import tempfile
import unittest

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (Activity, ActivityGenerator, AssessmentResource, AssessmentStaff, AssessmentStateSignOff,
                     Category, ModuleStaff, Programme, Staff, Task, TaskCompletion, WorkPackage)
from .testing import (add_assessment_staff, allocate, make_activity_type, make_group, make_module,
                      make_package, make_programme, make_resource_type, make_staff, make_state)

FORBIDDEN = reverse('forbidden')
ALLOCATION_PERMISSIONS = ('loads.add_modulestaff', 'loads.change_modulestaff', 'loads.delete_modulestaff')

MEDIA_ROOT = tempfile.mkdtemp(prefix='wam-tests-')


def tearDownModule():
    shutil.rmtree(MEDIA_ROOT, ignore_errors=True)


class ViewTestCase(TestCase):
    """A School group, its package, a module and a variety of people"""

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.group = make_group()
        self.package = make_package(group=self.group)
        self.other_package = make_package("Elsewhere", group=make_group("Elsewhere"))

        self.coordinator = make_staff('coordinator', package=self.package, group=self.group)
        self.lecturer = make_staff('lecturer', package=self.package, group=self.group)
        self.outsider = make_staff('outsider', package=self.other_package)
        self.superuser = make_staff('superuser', package=self.package, superuser=True)
        self.examiner = make_staff('examiner', package=self.package, is_external=True)

        self.module = make_module(self.package, coordinator=self.coordinator)
        self.module.lead_programme = make_programme(self.package, examiners=[self.examiner])
        self.module.save()

    def login(self, staff):
        self.client.force_login(staff.user)

    def assertForbidden(self, response):
        self.assertRedirects(response, FORBIDDEN, fetch_redirect_response=False)

    def assertNeedsLogin(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class AssessmentResourceViewTests(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.resource = AssessmentResource.objects.create(
            name="Exam paper", module=self.module, owner=self.lecturer, resource_type=make_resource_type(),
            resource=SimpleUploadedFile('exam.txt', b'Question 1'))

    def download(self):
        return self.client.get(reverse('download_assessment_resource', args=[self.resource.pk]))

    def delete(self, confirm=False):
        url = reverse('delete_assessment_resource', args=[self.resource.pk])
        return self.client.get(url + ('/confirm' if confirm else ''))

    def sign_off(self):
        return AssessmentStateSignOff.objects.create(module=self.module, assessment_state=make_state(),
                                                     signed_by=self.coordinator.user, notes="")

    def test_download(self):
        self.login(self.coordinator)
        response = self.download()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'Question 1')
        self.assertIn('exam', response['Content-Disposition'])
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.downloads, 1)

    def test_download_by_lead_examiner(self):
        self.login(self.examiner)
        self.assertEqual(self.download().status_code, 200)

    def test_download_forbidden(self):
        for staff in (self.outsider, make_staff('otherexaminer', is_external=True)):
            self.login(staff)
            self.assertForbidden(self.download())
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.downloads, 0)

    def test_download_needs_login(self):
        self.assertNeedsLogin(self.download())

    def test_download_missing_file(self):
        self.resource.resource.storage.delete(self.resource.resource.name)
        self.login(self.coordinator)
        self.assertEqual(self.download().status_code, 404)

    def test_delete_needs_confirmation(self):
        self.login(self.lecturer)
        response = self.delete()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AssessmentResource.objects.filter(pk=self.resource.pk).exists())

        response = self.delete(confirm=True)
        self.assertRedirects(response, reverse('modules_details', args=[self.module.pk]),
                             fetch_redirect_response=False)
        self.assertFalse(AssessmentResource.objects.filter(pk=self.resource.pk).exists())

    def test_coordinator_can_delete(self):
        self.login(self.coordinator)
        self.delete(confirm=True)
        self.assertFalse(AssessmentResource.objects.filter(pk=self.resource.pk).exists())

    def test_others_cannot_delete(self):
        for staff in (self.outsider, make_staff('colleague', group=self.group), self.examiner):
            self.login(staff)
            self.assertForbidden(self.delete(confirm=True))
        self.assertTrue(AssessmentResource.objects.filter(pk=self.resource.pk).exists())

    def test_signed_resources_only_deleted_by_superuser(self):
        self.sign_off()
        self.login(self.lecturer)
        self.assertForbidden(self.delete(confirm=True))
        self.login(self.superuser)
        self.delete(confirm=True)
        self.assertFalse(AssessmentResource.objects.filter(pk=self.resource.pk).exists())

    def delete_sign_off(self, signoff):
        return self.client.get(reverse('delete_assessment_sign_off', args=[signoff.pk]) + '/confirm')

    def test_superuser_deletes_latest_sign_off(self):
        signoff = self.sign_off()
        self.login(self.superuser)
        self.delete_sign_off(signoff)
        self.assertFalse(AssessmentStateSignOff.objects.filter(pk=signoff.pk).exists())

    def test_only_latest_sign_off_can_be_deleted(self):
        # The resource predates both sign offs, so only the newer sign off can block deletion
        AssessmentResource.objects.filter(pk=self.resource.pk).update(
            created=timezone.now() - datetime.timedelta(days=2))
        first = self.sign_off()
        AssessmentStateSignOff.objects.filter(pk=first.pk).update(
            created=timezone.now() - datetime.timedelta(days=1))
        self.sign_off()
        self.login(self.superuser)
        self.assertForbidden(self.delete_sign_off(first))
        self.assertTrue(AssessmentStateSignOff.objects.filter(pk=first.pk).exists())

    def test_sign_off_cannot_be_deleted_after_new_resources(self):
        signoff = self.sign_off()
        AssessmentStateSignOff.objects.filter(pk=signoff.pk).update(
            created=timezone.now() - datetime.timedelta(days=1))
        AssessmentResource.objects.create(name="Revised paper", module=self.module, owner=self.lecturer,
                                          resource_type=self.resource.resource_type,
                                          resource=SimpleUploadedFile('exam2.txt', b'Question 1a'))
        self.login(self.superuser)
        self.assertForbidden(self.delete_sign_off(signoff))
        self.assertTrue(AssessmentStateSignOff.objects.filter(pk=signoff.pk).exists())

    def test_sign_off_deletion_needs_permission(self):
        signoff = self.sign_off()
        self.login(self.coordinator)
        self.delete_sign_off(signoff)
        self.assertTrue(AssessmentStateSignOff.objects.filter(pk=signoff.pk).exists())

    @unittest.expectedFailure
    def test_staff_with_permission_can_delete_sign_off(self):
        """BUG: the view checks 'loads.del_assessmentstatesignoff', but Django's permission is
        'delete_assessmentstatesignoff', so only superusers can ever delete sign offs"""
        signoff = self.sign_off()
        admin = make_staff('schooladmin', group=self.group, is_staff=True,
                           permissions=['loads.delete_assessmentstatesignoff'])
        self.login(admin)
        self.delete_sign_off(signoff)
        self.assertFalse(AssessmentStateSignOff.objects.filter(pk=signoff.pk).exists())


def account_post(**kwargs):
    data = dict(username='newstaff', email='new.staff@example.ac.uk', title='Dr', first_name='New',
                last_name='Staff', password1='', password2='', staff_number='')
    data.update(kwargs)
    return data


class AccountCreationViewTests(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.admin = make_staff('schooladmin', group=self.group, is_staff=True,
                                permissions=['loads.add_staff', 'loads.add_externalexaminer'])

    def test_create_staff_user(self):
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse('create staff user')).status_code, 200)
        response = self.client.post(reverse('create staff user'),
                                    account_post(package=self.package.pk, groups=[self.group.pk]))
        self.assertRedirects(response, reverse('custom_admin_index'), fetch_redirect_response=False)
        staff = Staff.objects.get(user__username='newstaff')
        self.assertFalse(staff.is_external)
        self.assertIn(self.group, staff.user.groups.all())

    def test_invalid_form_is_redisplayed(self):
        self.login(self.admin)
        response = self.client.post(reverse('create staff user'), account_post(username='lecturer'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_groups_with_permissions_cannot_be_granted(self):
        """Otherwise admins could escalate privileges by adding people to powerful groups"""
        powerful = make_group("Powerful")
        powerful.permissions.add(Permission.objects.get(codename='delete_staff'))
        self.login(self.admin)
        response = self.client.post(reverse('create staff user'), account_post(groups=[powerful.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username='newstaff').exists())

    def test_non_admins_cannot_create_users(self):
        self.login(self.lecturer)
        self.assertEqual(self.client.post(reverse('create staff user'), account_post()).status_code, 403)
        self.assertEqual(self.client.post(reverse('create external examiner'), account_post()).status_code, 403)
        self.assertFalse(User.objects.filter(username='newstaff').exists())

    def test_admin_needs_permission(self):
        self.login(make_staff('weakadmin', is_staff=True))
        self.assertNeedsLogin(self.client.post(reverse('create staff user'), account_post()))
        self.assertFalse(User.objects.filter(username='newstaff').exists())

    def test_create_external_examiner(self):
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse('create external examiner')).status_code, 200)
        self.client.post(reverse('create external examiner'), account_post(username='newexaminer'))
        self.assertTrue(Staff.objects.get(user__username='newexaminer').is_external)


class TaskCompletionViewTests(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.task = Task.objects.create(name="Submit marks", details="", deadline=timezone.now(),
                                        category=Category.objects.create(name="Admin", abbreviation="admin",
                                                                         colour="blue"))
        self.task.targets.add(self.lecturer)

    def complete(self, staff):
        return self.client.post(reverse('tasks_completion', args=[self.task.pk, staff.pk]), {'comment': 'Done'})

    def test_complete_own_task(self):
        self.login(self.lecturer)
        self.assertEqual(self.client.get(reverse('tasks_completion', args=[self.task.pk, self.lecturer.pk]))
                         .status_code, 200)
        response = self.complete(self.lecturer)
        self.assertRedirects(response, reverse('tasks_details', args=[self.task.pk]),
                             fetch_redirect_response=False)
        self.assertEqual(TaskCompletion.objects.get(task=self.task).staff, self.lecturer)

    def test_cannot_complete_for_others(self):
        self.login(self.coordinator)
        self.assertForbidden(self.complete(self.lecturer))
        self.assertFalse(TaskCompletion.objects.exists())

    def test_complete_for_others_with_permission(self):
        self.login(make_staff('taskadmin', permissions=['loads.add_taskcompletion']))
        self.complete(self.lecturer)
        self.assertEqual(TaskCompletion.objects.get(task=self.task).staff, self.lecturer)


class WorkPackageViewTests(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.next_year = make_package("2018/19", group=self.group)

    def test_change_package(self):
        self.login(self.lecturer)
        self.client.get(reverse('workpackage_change'), HTTP_REFERER='/loads_charts/')
        response = self.client.post(reverse('workpackage_change'), {'package': self.next_year.pk})
        self.assertRedirects(response, '/loads_charts/', fetch_redirect_response=False)
        self.lecturer.refresh_from_db()
        self.assertEqual(self.lecturer.package, self.next_year)

    def test_change_package_ignores_unsafe_referer(self):
        self.login(self.lecturer)
        self.client.get(reverse('workpackage_change'), HTTP_REFERER='https://evil.example/')
        response = self.client.post(reverse('workpackage_change'), {'package': self.next_year.pk})
        self.assertRedirects(response, reverse('loads'), fetch_redirect_response=False)

    def test_change_package_without_session_next_page(self):
        """Error report: KeyError 'next_page' when the POST arrives without the GET having stored a
        next page in this session (a second tab, a double submit, or a session renewed by re-login)"""
        self.login(self.lecturer)
        response = self.client.post(reverse('workpackage_change') + '?next=/modules/index/',
                                    {'package': self.next_year.pk})
        self.assertRedirects(response, '/modules/index/', fetch_redirect_response=False)
        self.lecturer.refresh_from_db()
        self.assertEqual(self.lecturer.package, self.next_year)

    def test_change_package_twice_from_one_form(self):
        self.login(self.lecturer)
        self.client.get(reverse('workpackage_change'), HTTP_REFERER='/loads_charts/')
        self.client.post(reverse('workpackage_change'), {'package': self.next_year.pk})
        response = self.client.post(reverse('workpackage_change'), {'package': self.package.pk})
        self.assertRedirects(response, reverse('loads'), fetch_redirect_response=False)

    def test_change_package_ignores_unsafe_next(self):
        self.login(self.lecturer)
        response = self.client.post(reverse('workpackage_change') + '?next=https://evil.example/',
                                    {'package': self.next_year.pk})
        self.assertRedirects(response, reverse('loads'), fetch_redirect_response=False)

    def test_cannot_change_to_other_schools_package(self):
        self.login(self.lecturer)
        response = self.client.post(reverse('workpackage_change'), {'package': self.other_package.pk})
        self.assertEqual(response.status_code, 200)
        self.lecturer.refresh_from_db()
        self.assertEqual(self.lecturer.package, self.package)

    def migrate(self):
        return self.client.post(reverse('workpackage_migrate'), {
            'source_package': self.package.pk, 'destination_package': self.next_year.pk,
            'copy_programmes': 'on', 'copy_modules': 'on', 'copy_modulestaff': 'on'})

    def test_migrate(self):
        allocate(self.lecturer, self.module)
        self.login(self.superuser)
        self.assertEqual(self.client.get(reverse('workpackage_migrate')).status_code, 200)
        response = self.migrate()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Programme.objects.filter(package=self.next_year, programme_code='P1').exists())
        new_module = self.next_year.module_set.get(module_code=self.module.module_code)
        self.assertEqual(new_module.coordinator, self.coordinator)
        self.assertTrue(ModuleStaff.objects.filter(module=new_module, staff=self.lecturer).exists())
        self.assertEqual(self.package.module_set.count(), 1, "the source is untouched")

    def test_migrate_is_superuser_only(self):
        self.login(make_staff('schooladmin', group=self.group, is_staff=True))
        self.assertNeedsLogin(self.migrate())
        self.assertFalse(Programme.objects.filter(package=self.next_year).exists())


class AllocationViewTests(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.allocator = make_staff('allocator', package=self.package, group=self.group,
                                    permissions=ALLOCATION_PERMISSIONS)
        self.activity_type = make_activity_type()

    def module_url(self, package=None):
        return reverse('module_staff_allocation', args=[(package or self.package).pk, self.module.pk])

    def staff_url(self, staff, package=None):
        return reverse('staff_module_allocation', args=[(package or self.package).pk, staff.pk])

    @staticmethod
    def formset(field, rows, blank_rows=0):
        """POST data for an allocation formset. Like the real page, can include untouched blank rows"""
        data = {'form-TOTAL_FORMS': len(rows) + blank_rows, 'form-INITIAL_FORMS': 0,
                'form-MIN_NUM_FORMS': 0, 'form-MAX_NUM_FORMS': 1000}
        for i, (target, contact, admin, assessment) in enumerate(rows):
            data.update({f'form-{i}-id': '', f'form-{i}-{field}': target.pk,
                         f'form-{i}-contact_proportion': contact, f'form-{i}-admin_proportion': admin,
                         f'form-{i}-assessment_proportion': assessment})
        for i in range(len(rows), len(rows) + blank_rows):
            data.update({f'form-{i}-{name}': '' for name in
                         ('id', field, 'contact_proportion', 'admin_proportion', 'assessment_proportion')})
        return data

    def test_module_allocation_with_blank_row(self):
        """Error report: 'ModuleStaff has no staff' when the page submits an untouched blank row"""
        self.login(self.allocator)
        response = self.client.post(self.module_url(), self.formset('staff', [
            (self.lecturer, 40, 40, 40), (self.coordinator, 60, 60, 60)], blank_rows=1))
        self.assertRedirects(response, reverse('modules_details', args=[self.module.pk]),
                             fetch_redirect_response=False)
        self.assertEqual(ModuleStaff.objects.filter(module=self.module).count(), 2)

    def test_module_allocation_edit_and_delete(self):
        existing = allocate(self.lecturer, self.module, 100, 100, 100)
        self.login(self.allocator)
        data = {'form-TOTAL_FORMS': 2, 'form-INITIAL_FORMS': 1, 'form-MIN_NUM_FORMS': 0, 'form-MAX_NUM_FORMS': 1000,
                'form-0-id': existing.pk, 'form-0-staff': self.lecturer.pk, 'form-0-contact_proportion': 50,
                'form-0-admin_proportion': 50, 'form-0-assessment_proportion': 50, 'form-0-DELETE': 'on',
                'form-1-id': '', 'form-1-staff': self.coordinator.pk, 'form-1-contact_proportion': 100,
                'form-1-admin_proportion': 100, 'form-1-assessment_proportion': 100}
        self.client.post(self.module_url(), data)
        self.assertEqual(list(ModuleStaff.objects.values_list('staff', 'module', 'package')),
                         [(self.coordinator.pk, self.module.pk, self.package.pk)])

    def test_staff_allocation_with_blank_row(self):
        self.login(self.allocator)
        response = self.client.post(self.staff_url(self.lecturer), self.formset('module', [
            (self.module, 100, 100, 100)], blank_rows=1))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ModuleStaff.objects.filter(staff=self.lecturer).count(), 1)

    def test_allocate_staff_to_module(self):
        self.login(self.allocator)
        self.assertEqual(self.client.get(self.module_url()).status_code, 200)
        response = self.client.post(self.module_url(), self.formset('staff', [
            (self.lecturer, 60, 50, 50), (self.coordinator, 40, 50, 50)]))
        self.assertRedirects(response, reverse('modules_details', args=[self.module.pk]),
                             fetch_redirect_response=False)
        allocation = ModuleStaff.objects.get(staff=self.lecturer)
        self.assertEqual((allocation.module, allocation.package, allocation.contact_proportion),
                         (self.module, self.package, 60))

    def test_module_allocations_validated(self):
        self.login(self.allocator)
        for rows in ([(self.lecturer, 50, 50, 50), (self.lecturer, 10, 10, 10)],  # duplicate
                     [(self.lecturer, 60, 0, 0), (self.coordinator, 60, 0, 0)],  # over 100% contact
                     [(self.lecturer, 0, 0, 101)]):  # not a percentage
            response = self.client.post(self.module_url(), self.formset('staff', rows))
            self.assertEqual(response.status_code, 200, rows)
            self.assertTrue(response.context['formset'].non_form_errors() or
                            any(response.context['formset'].errors), rows)
        self.assertFalse(ModuleStaff.objects.exists())

    def test_module_allocation_permissions(self):
        self.login(self.lecturer)
        self.assertForbidden(self.client.get(self.module_url()))
        self.login(make_staff('outsideallocator', package=self.other_package, permissions=ALLOCATION_PERMISSIONS))
        self.assertForbidden(self.client.get(self.module_url()))

    def test_allocate_modules_to_staff(self):
        second = make_module(self.package, code="COM102")
        self.login(self.allocator)
        self.assertEqual(self.client.get(self.staff_url(self.lecturer)).status_code, 200)
        self.client.post(self.staff_url(self.lecturer), self.formset('module', [
            (self.module, 100, 100, 100), (second, 50, 50, 50)]))
        self.assertEqual(ModuleStaff.objects.filter(staff=self.lecturer, package=self.package).count(), 2)
        self.assertEqual(self.lecturer.total_hours(self.package),
                         self.module.get_all_hours() - self.module.get_coordinator_hours()
                         + (second.get_all_hours() - second.get_coordinator_hours()) / 2)

    def test_duplicate_modules_rejected(self):
        self.login(self.allocator)
        response = self.client.post(self.staff_url(self.lecturer), self.formset('module', [
            (self.module, 50, 50, 50), (self.module, 50, 50, 50)]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ModuleStaff.objects.exists())

    def test_staff_allocation_permissions(self):
        self.login(self.lecturer)
        self.assertNeedsLogin(self.client.get(self.staff_url(self.coordinator)))
        self.login(self.allocator)
        self.assertForbidden(self.client.get(self.staff_url(self.outsider)))
        self.assertForbidden(self.client.get(self.staff_url(self.lecturer, self.other_package)))


class ExternalViewTests(ViewTestCase):

    def test_examiner_sees_only_examined_modules(self):
        make_module(self.package, code="UNEXAMINED")
        self.login(self.examiner)
        response = self.client.get(reverse('external_modules_index', args=['']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.module.module_code)
        self.assertNotContains(response, "UNEXAMINED")

    def test_semester_filter(self):
        self.login(self.examiner)
        response = self.client.get(reverse('external_modules_index', args=['2']))
        self.assertNotContains(response, self.module.module_code)

    def test_staff_cannot_use_external_views(self):
        self.login(self.lecturer)
        self.assertEqual(self.client.get(reverse('external_modules_index', args=[''])).status_code, 403)


class AdminActionViewTests(ViewTestCase):

    def test_remove_assessment_staff(self):
        membership = add_assessment_staff(self.lecturer, self.package)
        self.login(make_staff('schooladmin', group=self.group, permissions=['loads.delete_assessmentstaff']))
        response = self.client.get(reverse('assessmentstaff_delete', args=[membership.pk]))
        self.assertRedirects(response, reverse('assessmentstaff_index'), fetch_redirect_response=False)
        self.assertFalse(AssessmentStaff.objects.exists())

    def test_cannot_remove_assessment_staff_in_other_package(self):
        membership = add_assessment_staff(self.outsider, self.other_package)
        self.login(make_staff('schooladmin', group=self.group, permissions=['loads.delete_assessmentstaff']))
        self.assertForbidden(self.client.get(reverse('assessmentstaff_delete', args=[membership.pk])))
        self.assertTrue(AssessmentStaff.objects.exists())

    def make_generator(self, package):
        generator = ActivityGenerator.objects.create(
            name="Open day", hours=5, percentage=0, semester='1', activity_type=make_activity_type(),
            package=package, details="")
        generator.groups.add(self.group)
        return generator

    def test_generate_activities(self):
        generator = self.make_generator(self.package)
        self.login(make_staff('schooladmin', group=self.group, permissions=['loads.add_activity']))
        response = self.client.get(reverse('generators_generate_activities', args=[generator.pk]))
        self.assertRedirects(response, reverse('generators_index'), fetch_redirect_response=False)
        self.assertEqual(Activity.objects.filter(staff=self.lecturer).count(), 1)

    def test_generate_activities_in_other_package(self):
        generator = self.make_generator(self.other_package)
        self.login(make_staff('schooladmin', group=self.group, permissions=['loads.add_activity']))
        self.assertForbidden(self.client.get(reverse('generators_generate_activities', args=[generator.pk])))
        self.assertFalse(Activity.objects.exists())


class AssessmentSignOffViewTests(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.ready = make_state("Ready", actors="coordinator", initial_state=True, priority=1)
        self.approved = make_state("Approved", actors="coordinator", initial_state=False, priority=2)
        self.ready.next_states.add(self.approved)

    def sign(self, state, module=None, url_module=None):
        url = reverse('add_assessment_sign_off', args=[(url_module or self.module).pk])
        return self.client.post(url, {'module': (module or self.module).pk, 'signed_by': self.coordinator.user.pk,
                                      'assessment_state': state.pk if state else '', 'notes': 'Moderated'})

    def test_sign_off(self):
        self.login(self.coordinator)
        self.assertEqual(self.client.get(reverse('add_assessment_sign_off', args=[self.module.pk])).status_code, 200)
        response = self.sign(self.ready)
        self.assertRedirects(response, reverse('modules_details', args=[self.module.pk]),
                             fetch_redirect_response=False)
        signoff = AssessmentStateSignOff.objects.get()
        self.assertEqual((signoff.assessment_state, signoff.signed_by), (self.ready, self.coordinator.user))

    def test_sign_off_without_choosing_a_state(self):
        """Error report: KeyError 'assessment_state' when the form is submitted with no state selected"""
        self.login(self.coordinator)
        response = self.sign(None)
        self.assertEqual(response.status_code, 200)
        self.assertIn('assessment_state', response.context['form'].errors)
        self.assertFalse(AssessmentStateSignOff.objects.exists())

    def test_cannot_skip_workflow_states(self):
        """Only the states that may follow the latest sign off can be chosen"""
        self.login(self.coordinator)
        response = self.sign(self.approved)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AssessmentStateSignOff.objects.exists())

        self.sign(self.ready)
        self.sign(self.approved)
        self.assertEqual(AssessmentStateSignOff.objects.count(), 2)

    def test_permission_is_checked_against_the_module_signed(self):
        """The hidden module field mustn't let permission on one module sign off another"""
        others_module = make_module(self.package, code="COM999", coordinator=self.lecturer)
        self.login(self.coordinator)
        response = self.sign(self.ready, module=self.module, url_module=others_module)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AssessmentStateSignOff.objects.exists())

    def test_cannot_choose_a_state_reserved_for_others(self):
        # The lecturer can set "Anyone", so gets the form, but "Ready" is for coordinators only
        make_state("Anyone", actors="anyone", initial_state=True, priority=3)
        self.login(self.lecturer)
        response = self.client.post(reverse('add_assessment_sign_off', args=[self.module.pk]),
                                    {'module': self.module.pk, 'signed_by': self.lecturer.user.pk,
                                     'assessment_state': self.ready.pk, 'notes': ''})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AssessmentStateSignOff.objects.exists())
