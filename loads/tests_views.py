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
        """Open the confirmation page, or submit it"""
        url = reverse('delete_assessment_resource', args=[self.resource.pk])
        if confirm:
            return self.client.post(url + '/confirm')
        return self.client.get(url)

    def sign_off(self):
        return AssessmentStateSignOff.objects.create(module=self.module, assessment_state=make_state(),
                                                     signed_by=self.coordinator.user, notes="")

    def test_download(self):
        self.login(self.coordinator)
        response = self.download()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'Question 1')
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

    def upload(self, name, content=b'data'):
        self.login(self.coordinator)
        return self.client.post(reverse('add_assessment_resource', args=[self.module.pk]),
                                {'name': name, 'details': '', 'resource_type': self.resource.resource_type.pk,
                                 'resource': SimpleUploadedFile(name, content)})

    def test_upload_allowed_types(self):
        for name in ('paper.docx', 'marking.pdf', 'capture.pcap', 'model.igs', 'notebook.ipynb', 'NOEXTENSION'):
            response = self.upload(name)
            self.assertEqual(response.status_code, 302, name)
        self.assertEqual(AssessmentResource.objects.count(), 7)

    def test_upload_refuses_dangerous_types(self):
        for name in ('paper.html', 'PAPER.HTM', 'diagram.svg', 'run.exe', 'link.url', 'paper.pdf.html', 'macro.docm',
                     'sheet.XLSM'):
            response = self.upload(name)
            self.assertEqual(response.status_code, 200, name)
            self.assertIn('resource', response.context['form'].errors, name)
        self.assertEqual(AssessmentResource.objects.count(), 1)

    @override_settings(WAM_ASSESSMENT_MAX_UPLOAD_MB=1)
    def test_upload_size_limit(self):
        response = self.upload('big.pdf', b'x' * (1024 * 1024 + 1))
        self.assertIn('at most 1 MB', str(response.context['form'].errors['resource']))
        self.assertEqual(self.upload('small.pdf', b'x' * 1024).status_code, 302)

    def serve(self, name):
        resource = AssessmentResource.objects.create(
            name=name, module=self.module, owner=self.lecturer, resource_type=self.resource.resource_type,
            resource=SimpleUploadedFile(name, b'<script>alert(1)</script>'))
        self.login(self.coordinator)
        return self.client.get(reverse('download_assessment_resource', args=[resource.pk]))

    def test_web_pages_always_download(self):
        """Including any uploaded before uploads were restricted"""
        for name in ('legacy.html', 'legacy.svg', 'legacy.xhtml'):
            response = self.serve(name)
            self.assertEqual(response['Content-Type'], 'application/octet-stream', name)
            self.assertTrue(response['Content-Disposition'].startswith('attachment'), name)

    def test_pdfs_and_images_open_in_the_browser(self):
        response = self.serve('paper.pdf')
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('inline'))
        self.assertNotIn('Content-Security-Policy', response)

        response = self.serve('figure.png')
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response['Content-Security-Policy'], 'sandbox')

    def test_code_is_shown_as_plain_text(self):
        for name in ('solution.py', 'notebook.ipynb', 'data.json'):
            response = self.serve(name)
            self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8', name)
            self.assertEqual(response['Content-Security-Policy'], 'sandbox', name)

    def test_office_files_download(self):
        response = self.serve('paper.docx')
        self.assertEqual(response['Content-Type'], 'application/octet-stream')
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))

    def test_awkward_filenames_are_encoded(self):
        response = self.serve('Exam "final" résumé.pdf')
        self.assertNotIn('"final"', response['Content-Disposition'])
        self.assertIn("filename*=utf-8''", response['Content-Disposition'])

    def delete_sign_off(self, signoff):
        return self.client.post(reverse('delete_assessment_sign_off', args=[signoff.pk]) + '/confirm')

    def test_links_cannot_delete(self):
        """Audit item 3: following the confirm link (a GET) only shows the confirmation page"""
        signoff = self.sign_off()
        self.login(self.superuser)
        response = self.client.get(reverse('delete_assessment_resource', args=[self.resource.pk]) + '/confirm')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'method="post"')
        self.assertTrue(AssessmentResource.objects.filter(pk=self.resource.pk).exists())

        response = self.client.get(reverse('delete_assessment_sign_off', args=[signoff.pk]) + '/confirm')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AssessmentStateSignOff.objects.filter(pk=signoff.pk).exists())

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
        response = self.client.post(reverse('assessmentstaff_delete', args=[membership.pk]))
        self.assertRedirects(response, reverse('assessmentstaff_index'), fetch_redirect_response=False)
        self.assertFalse(AssessmentStaff.objects.exists())

    def test_cannot_remove_assessment_staff_in_other_package(self):
        membership = add_assessment_staff(self.outsider, self.other_package)
        self.login(make_staff('schooladmin', group=self.group, permissions=['loads.delete_assessmentstaff']))
        self.assertForbidden(self.client.post(reverse('assessmentstaff_delete', args=[membership.pk])))
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
        response = self.client.post(reverse('generators_generate_activities', args=[generator.pk]))
        self.assertRedirects(response, reverse('generators_index'), fetch_redirect_response=False)
        self.assertEqual(Activity.objects.filter(staff=self.lecturer).count(), 1)

    def test_generate_activities_in_other_package(self):
        generator = self.make_generator(self.other_package)
        self.login(make_staff('schooladmin', group=self.group, permissions=['loads.add_activity']))
        self.assertForbidden(self.client.post(reverse('generators_generate_activities', args=[generator.pk])))
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


class PackageRestrictionViewTests(ViewTestCase):
    """Choices offered in forms should be limited to the user's current package"""

    def setUp(self):
        super().setUp()
        self.allocator = make_staff('allocator', package=self.package, group=self.group,
                                    permissions=ALLOCATION_PERMISSIONS + ('loads.add_activity', 'loads.change_activity'))
        self.foreign_module = make_module(self.other_package, code="FOREIGN")
        self.activity_type = make_activity_type()

    def test_staff_allocation_only_offers_package_modules(self):
        """Known bug: the 'add a module' row offered modules from every package"""
        allocate(self.lecturer, self.module)
        self.login(self.allocator)
        response = self.client.get(reverse('staff_module_allocation', args=[self.package.pk, self.lecturer.pk]))
        formset = response.context['formset']
        self.assertEqual(list(formset.empty_form.fields['module'].queryset), [self.module])
        self.assertEqual(list(formset.forms[0].fields['module'].queryset), [self.module])
        self.assertNotContains(response, "FOREIGN")

    def test_staff_allocation_rejects_other_package_modules(self):
        self.login(self.allocator)
        data = {'form-TOTAL_FORMS': 1, 'form-INITIAL_FORMS': 0, 'form-MIN_NUM_FORMS': 0, 'form-MAX_NUM_FORMS': 1000,
                'form-0-id': '', 'form-0-module': self.foreign_module.pk, 'form-0-contact_proportion': 100,
                'form-0-admin_proportion': 100, 'form-0-assessment_proportion': 100}
        response = self.client.post(reverse('staff_module_allocation', args=[self.package.pk, self.lecturer.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ModuleStaff.objects.exists())

    def activity_post(self, staff):
        return {'name': 'Open day', 'hours_percentage_combined_0': 'H', 'hours_percentage_combined_1': 10,
                'hours_percentage_combined_2': '', 'semester_1': 'on', 'activity_type': self.activity_type.pk,
                'module': '', 'staff': staff.pk, 'comment': ''}

    def test_create_activity_only_offers_package_staff_and_modules(self):
        """Known bug: the staff list on /activities/create/ wasn't restricted, unlike editing"""
        self.login(self.allocator)
        form = self.client.get(reverse('create activity')).context['form']
        self.assertNotIn(self.outsider, form.fields['staff'].queryset)
        self.assertIn(self.lecturer, form.fields['staff'].queryset)
        self.assertEqual(list(form.fields['module'].queryset), [self.module])
        self.assertEqual(form['semester'].value(), '1,2,3')

    def test_create_activity(self):
        self.login(self.allocator)
        response = self.client.post(reverse('create activity'), self.activity_post(self.lecturer))
        self.assertRedirects(response, reverse('activities_index'), fetch_redirect_response=False)
        activity = Activity.objects.get()
        self.assertEqual((activity.staff, activity.package, activity.hours, activity.semester),
                         (self.lecturer, self.package, 10, '1'))

    def test_create_activity_rejects_staff_outside_package(self):
        self.login(self.allocator)
        response = self.client.post(reverse('create activity'), self.activity_post(self.outsider))
        self.assertEqual(response.status_code, 200)
        self.assertIn('staff', response.context['form'].errors)
        self.assertFalse(Activity.objects.exists())


    def test_module_allocation_rejects_staff_outside_package(self):
        """The staff restriction used to be applied after the formset had already been validated"""
        self.login(self.allocator)
        data = {'form-TOTAL_FORMS': 1, 'form-INITIAL_FORMS': 0, 'form-MIN_NUM_FORMS': 0, 'form-MAX_NUM_FORMS': 1000,
                'form-0-id': '', 'form-0-staff': self.outsider.pk, 'form-0-contact_proportion': 100,
                'form-0-admin_proportion': 100, 'form-0-assessment_proportion': 100}
        response = self.client.post(reverse('module_staff_allocation', args=[self.package.pk, self.module.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ModuleStaff.objects.exists())
        self.assertNotIn(self.outsider, response.context['formset'].empty_form.fields['staff'].queryset)


class ModuleDetailsViewTests(ViewTestCase):

    def test_shows_number_of_students(self):
        """Known bug: showed the deprecated ModuleSize, so "None" for modules without one"""
        self.login(self.coordinator)
        response = self.client.get(reverse('modules_details', args=[self.module.pk]))
        self.assertContains(response, "Number of students")
        self.assertNotContains(response, ">None<")
        self.assertContains(response, str(self.module.number_students))


class ProjectDetailsViewTests(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.admin = make_staff('projectadmin', package=self.package, group=self.group, is_staff=True, permissions=(
            'loads.change_project', 'loads.add_projectstaff', 'loads.change_projectstaff',
            'loads.delete_projectstaff'))
        from .models import Body, Project
        self.project = Project.objects.create(name="Grant", body=Body.objects.create(name="Funder", details=""),
                                              activity_type=make_activity_type(),
                                              start=datetime.date(2017, 9, 1), end=datetime.date(2018, 8, 31))

    def post(self, rows, blank_rows=0):
        data = {'name': self.project.name, 'activity_type': self.project.activity_type.pk,
                'body': self.project.body.pk, 'start': '2017-09-01', 'end': '2018-08-31',
                'form-TOTAL_FORMS': len(rows) + blank_rows, 'form-INITIAL_FORMS': 0,
                'form-MIN_NUM_FORMS': 0, 'form-MAX_NUM_FORMS': 1000}
        for i, staff in enumerate(rows):
            data.update({f'form-{i}-id': '', f'form-{i}-staff': staff.pk, f'form-{i}-start': '2017-09-01',
                         f'form-{i}-end': '2018-08-31', f'form-{i}-hours_per_week': 2})
        for i in range(len(rows), len(rows) + blank_rows):
            data.update({f'form-{i}-{name}': '' for name in ('id', 'staff', 'start', 'end', 'hours_per_week')})
        return self.client.post(reverse('projects_details', args=[self.project.pk]), data)

    def test_allocate_staff_with_blank_row(self):
        from .models import ProjectStaff
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse('projects_details', args=[self.project.pk])).status_code, 200)
        response = self.post([self.lecturer], blank_rows=1)
        self.assertRedirects(response, reverse('projects_index'), fetch_redirect_response=False)
        self.assertEqual(list(ProjectStaff.objects.values_list('staff', 'project')),
                         [(self.lecturer.pk, self.project.pk)])

    def test_rejects_staff_outside_packages(self):
        from .models import ProjectStaff
        self.login(self.admin)
        response = self.post([self.outsider])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ProjectStaff.objects.exists())


class EditOtherSchoolsRecordsTests(ViewTestCase):
    """Audit item 1: edit pages must not reach records outside the user's packages"""

    def setUp(self):
        super().setUp()
        self.activity_type = make_activity_type()
        self.admin = make_staff('schooladmin', package=self.package, group=self.group, permissions=[
            'loads.change_module', 'loads.change_activity', 'loads.change_programme', 'loads.change_task',
            'loads.change_activitygenerator'])
        # Records belonging to the other School
        self.their_module = make_module(self.other_package, code="THEIRS")
        self.their_activity = Activity.objects.create(name="Theirs", hours=5, percentage=0, package=self.other_package,
                                                      activity_type=self.activity_type, staff=self.outsider)
        self.their_programme = Programme.objects.create(programme_code="T1", programme_name="Theirs",
                                                        package=self.other_package)
        self.their_generator = ActivityGenerator.objects.create(
            name="Theirs", hours=5, percentage=0, semester='1', activity_type=self.activity_type,
            package=self.other_package, details="")
        self.category = Category.objects.create(name="Admin", abbreviation="admin", colour="blue")
        self.their_task = Task.objects.create(name="Theirs", details="", deadline=timezone.now(), category=self.category)
        self.their_task.targets.add(self.outsider)

    def module_post(self, module, code):
        return {'module_code': code, 'module_name': 'Changed', 'campus': module.campus.pk, 'credits': 20,
                'number_students': 5, 'semester_1': 'on', 'coordinator_hours': '', 'contact_hours': '',
                'admin_hours': '', 'assessment_hours': '', 'coordinator': '', 'lead_programme': '', 'details': ''}

    def activity_post(self, name, staff=''):
        return {'name': name, 'hours_percentage_combined_0': 'H', 'hours_percentage_combined_1': 7,
                'hours_percentage_combined_2': '', 'semester_1': 'on', 'activity_type': self.activity_type.pk,
                'module': '', 'staff': staff, 'comment': ''}

    def test_other_schools_records_are_not_found(self):
        self.login(self.admin)
        for name, obj in (('update module', self.their_module), ('update activity', self.their_activity),
                          ('update programme', self.their_programme), ('update generator', self.their_generator),
                          ('update task', self.their_task)):
            self.assertEqual(self.client.get(reverse(name, args=[obj.pk])).status_code, 404, name)
            self.assertEqual(self.client.post(reverse(name, args=[obj.pk]), {'name': 'Hacked'}).status_code, 404, name)

    def test_other_schools_module_unchanged(self):
        """Confirmed in the audit: another School's module could be renamed"""
        self.login(self.admin)
        self.client.post(reverse('update module', args=[self.their_module.pk]),
                         self.module_post(self.their_module, 'HACKED'))
        self.their_module.refresh_from_db()
        self.assertEqual(self.their_module.module_code, 'THEIRS')

    def test_other_schools_activity_not_moved(self):
        """Confirmed in the audit: editing another School's activity moved it into the editor's package"""
        self.login(self.admin)
        self.client.post(reverse('update activity', args=[self.their_activity.pk]), self.activity_post('Moved'))
        self.their_activity.refresh_from_db()
        self.assertEqual((self.their_activity.package, self.their_activity.name), (self.other_package, 'Theirs'))

    def test_own_records_in_another_package_stay_put(self):
        """Editing a record in one of your packages, while another is selected, mustn't move it"""
        next_year = make_package("2018/19", group=self.group)
        activity = Activity.objects.create(name="Next year", hours=5, percentage=0, package=next_year,
                                           activity_type=self.activity_type, staff=self.lecturer)
        self.login(self.admin)  # current package is self.package
        form = self.client.get(reverse('update activity', args=[activity.pk])).context['form']
        self.assertEqual(list(form.fields['module'].queryset), [])  # next year's modules, not this year's
        response = self.client.post(reverse('update activity', args=[activity.pk]),
                                    self.activity_post('Next year, edited', staff=self.lecturer.pk))
        self.assertEqual(response.status_code, 302)
        activity.refresh_from_db()
        self.assertEqual((activity.package, activity.name, activity.hours), (next_year, 'Next year, edited', 7))

    def test_own_generator_keeps_its_package(self):
        next_year = make_package("2018/19", group=self.group)
        generator = ActivityGenerator.objects.create(name="Open day", hours=5, percentage=0, semester='1',
                                                     activity_type=self.activity_type, package=next_year, details="")
        self.login(self.admin)
        response = self.client.post(reverse('update generator', args=[generator.pk]), {
            'name': 'Open day, edited', 'hours_percentage_combined_0': 'H', 'hours_percentage_combined_1': 3,
            'hours_percentage_combined_2': '', 'semester_1': 'on', 'activity_type': self.activity_type.pk,
            'module': '', 'comment': '', 'package': self.other_package.pk, 'details': 'Annual event'})
        self.assertEqual(response.status_code, 302)
        generator.refresh_from_db()
        self.assertEqual((generator.package, generator.name), (next_year, 'Open day, edited'))

    def test_own_module_can_be_edited(self):
        self.login(self.admin)
        response = self.client.post(reverse('update module', args=[self.module.pk]),
                                    self.module_post(self.module, 'COM101X'))
        self.assertEqual(response.status_code, 302)
        self.module.refresh_from_db()
        self.assertEqual((self.module.module_code, self.module.package), ('COM101X', self.package))

    def test_superuser_can_edit_any_school(self):
        self.login(self.superuser)
        self.client.post(reverse('update module', args=[self.their_module.pk]),
                         self.module_post(self.their_module, 'FIXED'))
        self.their_module.refresh_from_db()
        self.assertEqual((self.their_module.module_code, self.their_module.package), ('FIXED', self.other_package))

    def test_shared_task_keeps_other_schools_targets(self):
        """A task aimed at both Schools can be edited, without dropping the targets the editor can't see"""
        self.their_task.targets.add(self.lecturer)
        self.login(self.admin)
        response = self.client.post(reverse('update task', args=[self.their_task.pk]), {
            'name': 'Shared, edited', 'category': self.category.pk, 'details': 'x',
            'deadline': '2030-01-01T09:00', 'targets': [self.lecturer.pk, self.coordinator.pk]})
        self.assertEqual(response.status_code, 302)
        self.their_task.refresh_from_db()
        self.assertEqual(self.their_task.name, 'Shared, edited')
        self.assertCountEqual(self.their_task.targets.all(), [self.outsider, self.lecturer, self.coordinator])


class ActionsNeedAFormTests(ViewTestCase):
    """Audit item 3: actions that change data can't be triggered by following a link (a GET)"""

    def setUp(self):
        super().setUp()
        from .models import Body, Project, ProjectStaff
        self.admin = make_staff('schooladmin', package=self.package, group=self.group, is_staff=True, permissions=(
            'loads.view_assessmentstaff', 'loads.add_assessmentstaff', 'loads.delete_assessmentstaff',
            'loads.add_activity', 'loads.add_projectstaff',
            'loads.change_projectstaff', 'loads.delete_projectstaff'))
        self.membership = add_assessment_staff(self.lecturer, self.package)
        activity_type = make_activity_type()
        self.generator = ActivityGenerator.objects.create(name="Open day", hours=5, percentage=0, semester='1',
                                                          activity_type=activity_type, package=self.package,
                                                          details="")
        self.generator.groups.add(self.group)
        self.project = Project.objects.create(name="Grant", body=Body.objects.create(name="Funder", details=""),
                                              activity_type=activity_type, start=self.package.startdate,
                                              end=self.package.enddate)
        ProjectStaff.objects.create(staff=self.lecturer, project=self.project, hours_per_week=2,
                                    start=self.package.startdate, end=self.package.enddate)
        self.login(self.admin)

    def test_get_is_refused(self):
        for name, pk in (('assessmentstaff_delete', self.membership.pk),
                         ('generators_generate_activities', self.generator.pk),
                         ('projects_generate_activities', self.project.pk)):
            self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 405, name)
        self.assertTrue(AssessmentStaff.objects.filter(pk=self.membership.pk).exists())
        self.assertFalse(Activity.objects.exists())

    def test_post_works(self):
        self.client.post(reverse('assessmentstaff_delete', args=[self.membership.pk]))
        self.assertFalse(AssessmentStaff.objects.filter(pk=self.membership.pk).exists())
        self.client.post(reverse('generators_generate_activities', args=[self.generator.pk]))
        self.assertTrue(Activity.objects.filter(name="Open day").exists())
        response = self.client.post(reverse('projects_generate_activities', args=[self.project.pk]))
        self.assertRedirects(response, reverse('projects_index'), fetch_redirect_response=False)
        self.assertTrue(Activity.objects.filter(name="Grant (Funder)").exists())

    def test_pages_offer_forms_not_links(self):
        """The buttons on each page submit forms, with the CSRF token"""
        for page, action in ((reverse('assessmentstaff_index'), reverse('assessmentstaff_delete', args=[self.membership.pk])),
                             (reverse('generators_index'), reverse('generators_generate_activities', args=[self.generator.pk])),
                             (reverse('projects_index'), reverse('projects_generate_activities', args=[self.project.pk]))):
            content = self.client.get(page).content.decode()
            self.assertIn(f'action="{action}"', content, page)
            self.assertNotIn(f'href="{action}"', content, page)
            self.assertIn('csrfmiddlewaretoken', content, page)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class AuditQuickFixTests(ViewTestCase):
    """Smaller items from the security audit"""

    def test_module_details_refuses_users_without_staff(self):
        """Item 4: this used to show any module"""
        user = User.objects.create_user('nostaff')
        Staff.objects.filter(user=user).delete()
        self.client.force_login(user)
        self.assertForbidden(self.client.get(reverse('modules_details', args=[self.module.pk])))

    def test_migration_results_escape_names(self):
        """Item 5: a module name containing script was output unescaped to the superuser"""
        self.module.module_name = '<script>alert(1)</script>'
        self.module.save()
        allocate(self.lecturer, self.module)
        next_year = make_package("2018/19", group=self.group)
        self.login(self.superuser)
        response = self.client.post(reverse('workpackage_migrate'), {
            'source_package': self.package.pk, 'destination_package': next_year.pk,
            'copy_programmes': 'on', 'copy_modules': 'on'})
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')

    def test_team_members_and_assessment_staff_can_upload(self):
        """Their access was checked by comparing different kinds of record, so they always got 403"""
        allocate(self.lecturer, self.module)
        assessor = make_staff('assessor', package=self.package, group=self.group)
        add_assessment_staff(assessor, self.package)
        resource_type = make_resource_type()
        for staff in (self.lecturer, assessor):
            self.login(staff)
            response = self.client.post(reverse('add_assessment_resource', args=[self.module.pk]),
                                        {'name': f'By {staff}', 'details': '', 'resource_type': resource_type.pk,
                                         'resource': SimpleUploadedFile('paper.pdf', b'%PDF')})
            self.assertEqual(response.status_code, 302, staff)
        self.assertEqual(AssessmentResource.objects.count(), 2)

    def test_others_still_cannot_upload(self):
        colleague = make_staff('colleague', package=self.package, group=self.group)
        self.login(colleague)
        self.assertEqual(self.client.get(reverse('add_assessment_resource', args=[self.module.pk])).status_code, 403)

    def test_assessment_team_only_accepts_package_staff(self):
        """Item 8: the staff choices were only restricted when the page was shown, not when submitted"""
        admin = make_staff('schooladmin', package=self.package, group=self.group,
                           permissions=['loads.view_assessmentstaff', 'loads.add_assessmentstaff'])
        self.login(admin)
        response = self.client.post(reverse('assessmentstaff_index'),
                                    {'staff': self.outsider.pk, 'package': self.package.pk})
        self.assertEqual(response.status_code, 200)
        self.assertIn('staff', response.context['form'].errors)
        self.assertFalse(AssessmentStaff.objects.exists())

        self.client.post(reverse('assessmentstaff_index'), {'staff': self.lecturer.pk, 'package': self.package.pk})
        self.assertTrue(AssessmentStaff.objects.filter(staff=self.lecturer, package=self.package).exists())

    def test_loads_by_modules_checks_the_package(self):
        """Item 7: the same check as the other loads pages"""
        self.lecturer.package = self.other_package
        self.lecturer.save()
        self.login(self.lecturer)
        response = self.client.get(reverse('loads_modules', args=['']))
        self.assertRedirects(response, reverse('workpackage_change'), fetch_redirect_response=False)

        self.lecturer.package = None
        self.lecturer.save()
        response = self.client.get(reverse('loads_modules', args=['']))
        self.assertRedirects(response, reverse('workpackage_change'), fetch_redirect_response=False)

        self.lecturer.package = self.package
        self.lecturer.save()
        self.assertEqual(self.client.get(reverse('loads_modules', args=[''])).status_code, 200)
