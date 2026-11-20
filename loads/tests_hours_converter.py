"""Tests for entering a module's hours per person"""
from decimal import Decimal as D

from django.contrib.admin.models import LogEntry
from django.test import SimpleTestCase

from WAM.settings import WAM_DEFAULT_ACTIVITY_TYPE
from django.urls import reverse

from .hours_converter import Plan, percentages, whole
from .models import ActivityType, Category, ModuleStaff
from .testing import make_module, make_staff
from .tests_views import ViewTestCase

PERMISSIONS = ['loads.change_module', 'loads.add_modulestaff', 'loads.change_modulestaff',
               'loads.delete_modulestaff']


class ArithmeticTests(SimpleTestCase):

    def test_percentages_add_up_to_100(self):
        self.assertEqual(percentages([D(10), D(10), D(10)]), [34, 33, 33])
        self.assertEqual(percentages([D(1), D(2)]), [33, 67])
        self.assertEqual(percentages([D('7.5'), D('2.5')]), [75, 25])
        for hours in ([D(1)] * 7, [D(3), D(5), D(11), D(13)], [D('0.5'), D(99)]):
            self.assertEqual(sum(percentages(hours)), 100, hours)

    def test_no_hours(self):
        self.assertEqual(percentages([D(0), D(0)]), [0, 0])
        self.assertEqual(percentages([]), [])

    def test_whole_hours_round_halves_up(self):
        self.assertEqual([whole(D('2.5')), whole(D('3.5')), whole(D('3.4'))], [3, 4, 3])


class HoursByPersonTestCase(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.admin = make_staff('schooladmin', group=self.group, permissions=PERMISSIONS)
        self.url = reverse('module_hours_by_person', args=[self.module.pk])
        # New allocations get the default activity type, as on the allocations page
        category = Category.objects.create(name="Education", abbreviation="edu", colour="red")
        ActivityType.objects.get_or_create(pk=WAM_DEFAULT_ACTIVITY_TYPE,
                                           defaults={'name': "Module teaching", 'category': category})

    def post(self, rows, initial=0, **extra):
        data = {'hours-TOTAL_FORMS': str(len(rows)), 'hours-INITIAL_FORMS': str(initial),
                'hours-MIN_NUM_FORMS': '0', 'hours-MAX_NUM_FORMS': '1000'}
        for i, row in enumerate(rows):
            staff, contact, assessment, admin = row[:4]
            data.update({f'hours-{i}-staff': staff.pk if staff else '', f'hours-{i}-contact': contact,
                         f'hours-{i}-assessment': assessment, f'hours-{i}-admin': admin})
            if len(row) > 4 and row[4]:
                data[f'hours-{i}-DELETE'] = 'on'
        data.update(extra)
        return self.client.post(self.url, data)

    def confirm(self, rows, **extra):
        preview = self.post(rows)
        return self.post(rows, confirm='1', fingerprint=preview.context['plan'].fingerprint(), **extra)


class PlanTests(HoursByPersonTestCase):

    def test_totals_shares_and_rounding(self):
        plan = Plan(self.module, [(self.coordinator, {'contact': D(10), 'assessment': D('7.5'), 'admin': D(0)}),
                                  (self.lecturer, {'contact': D(20), 'assessment': D(0), 'admin': D(0)}),
                                  (self.admin, {'contact': D(0), 'assessment': D(0), 'admin': D(0)})])
        self.assertEqual(plan.totals, {'contact': 30, 'assessment': 8, 'admin': 0})
        self.assertEqual([(p['contact'], p['assessment'], p['admin']) for p in plan.people],
                         [(33, 100, 0), (67, 0, 0)])
        self.assertEqual(plan.dropped, [self.admin])
        self.assertTrue(plan.rounded)
        exact = Plan(self.module, [(self.coordinator, {'contact': D(25), 'assessment': D(5), 'admin': D(2)}),
                                   (self.lecturer, {'contact': D(75), 'assessment': D(15), 'admin': D(2)})])
        self.assertFalse(exact.rounded)


class HoursByPersonPageTests(HoursByPersonTestCase):

    def test_who_can_use_it(self):
        self.login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.login(self.superuser)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        for staff in (self.lecturer,
                      make_staff('partial', group=self.group, permissions=PERMISSIONS[1:]),  # can't change the module
                      make_staff('elsewhere', package=self.other_package, permissions=PERMISSIONS)):
            self.login(staff)
            self.assertRedirects(self.client.get(self.url), reverse('forbidden'), fetch_redirect_response=False)
            self.assertRedirects(self.post([(staff, 10, 0, 0)]), reverse('forbidden'), fetch_redirect_response=False)

    def test_module_page_links_to_it_for_those_who_may(self):
        self.login(self.admin)
        self.assertContains(self.client.get(reverse('modules_details', args=[self.module.pk])), self.url)
        self.login(self.lecturer)
        self.assertNotContains(self.client.get(reverse('modules_details', args=[self.module.pk])), self.url)

    def test_starts_from_current_allocations_as_hours(self):
        self.module.contact_hours, self.module.assessment_hours, self.module.admin_hours = 40, 20, 10
        self.module.save()
        ModuleStaff.objects.create(module=self.module, staff=self.lecturer, package=self.package,
                                   contact_proportion=25, assessment_proportion=50, admin_proportion=100)
        self.login(self.admin)
        initial = self.client.get(self.url).context['formset'].initial
        self.assertEqual(initial, [{'staff': self.lecturer, 'contact': 10.0, 'assessment': 10.0, 'admin': 10.0}])

    def test_preview_changes_nothing(self):
        self.login(self.admin)
        response = self.post([(self.coordinator, 10, 5, 2), (self.lecturer, 30, 15, 0)])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['plan'].totals, {'contact': 40, 'assessment': 20, 'admin': 2})
        self.assertContains(response, "Saving will replace")
        self.module.refresh_from_db()
        self.assertIsNone(self.module.contact_hours)
        self.assertFalse(ModuleStaff.objects.filter(module=self.module).exists())

    def test_confirming_replaces_hours_and_allocations(self):
        old_type = ActivityType.objects.create(name="Other teaching",
                                               category=Category.objects.get(name="Education"))
        ModuleStaff.objects.create(module=self.module, staff=self.lecturer, package=self.package,
                                   activity_type=old_type, contact_proportion=100, assessment_proportion=100,
                                   admin_proportion=100)
        ModuleStaff.objects.create(module=self.module, staff=self.superuser, package=self.package,
                                   contact_proportion=0, assessment_proportion=0, admin_proportion=0)
        self.login(self.admin)
        response = self.confirm([(self.coordinator, 10, 5, 2), (self.lecturer, 30, 15, 0)])
        self.assertRedirects(response, reverse('modules_details', args=[self.module.pk]), fetch_redirect_response=False)

        self.module.refresh_from_db()
        self.assertEqual((self.module.contact_hours, self.module.assessment_hours, self.module.admin_hours), (40, 20, 2))
        allocations = {a.staff: a for a in ModuleStaff.objects.filter(module=self.module)}
        self.assertEqual(set(allocations), {self.coordinator, self.lecturer})  # the superuser's is gone
        coordinator, lecturer = allocations[self.coordinator], allocations[self.lecturer]
        self.assertEqual((coordinator.contact_proportion, coordinator.assessment_proportion, coordinator.admin_proportion),
                         (25, 25, 100))
        self.assertEqual((lecturer.contact_proportion, lecturer.assessment_proportion, lecturer.admin_proportion),
                         (75, 75, 0))
        self.assertEqual(lecturer.activity_type, old_type)  # kept
        self.assertEqual(coordinator.package, self.package)
        self.assertIn("Hours entered per person", LogEntry.objects.get().change_message)

    def test_people_with_no_hours_get_no_allocation(self):
        self.login(self.admin)
        self.confirm([(self.coordinator, 10, 0, 0), (self.lecturer, 0, 0, 0)])
        self.assertEqual(list(ModuleStaff.objects.filter(module=self.module).values_list('staff', flat=True)),
                         [self.coordinator.pk])

    def test_deleted_rows_are_left_out(self):
        self.login(self.admin)
        self.confirm([(self.coordinator, 10, 0, 0), (self.lecturer, 30, 0, 0, True)])
        allocation = ModuleStaff.objects.get(module=self.module)
        self.assertEqual((allocation.staff, allocation.contact_proportion), (self.coordinator, 100))

    def test_figures_changed_after_preview_are_not_saved(self):
        self.login(self.admin)
        preview = self.post([(self.coordinator, 10, 0, 0)])
        response = self.post([(self.coordinator, 99, 0, 0)], confirm='1',
                             fingerprint=preview.context['plan'].fingerprint())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "changed after the preview")
        self.assertFalse(ModuleStaff.objects.filter(module=self.module).exists())

    def test_someone_listed_twice(self):
        self.login(self.admin)
        response = self.post([(self.coordinator, 10, 0, 0), (self.coordinator, 5, 0, 0)])
        self.assertIsNone(response.context['plan'])
        self.assertContains(response, "listed more than once")

    def test_no_hours_at_all(self):
        self.login(self.admin)
        response = self.post([(self.coordinator, 0, 0, 0)])
        self.assertContains(response, "Enter some hours")

    def test_blank_extra_row_is_ignored(self):
        self.login(self.admin)
        response = self.post([(self.coordinator, 10, 0, 0), (None, '0', '0', '0')])
        self.assertEqual(len(response.context['plan'].people), 1)

    def test_only_internal_staff_can_be_chosen(self):
        self.login(self.admin)
        response = self.post([(self.examiner, 10, 0, 0)])
        self.assertIsNone(response.context['plan'])

    def test_staff_from_other_packages_cannot_be_chosen(self):
        self.login(self.admin)
        self.assertIsNone(self.post([(self.outsider, 10, 0, 0)]).context['plan'])

    def test_other_modules_untouched(self):
        other = make_module(self.package, code="COM777")
        ModuleStaff.objects.create(module=other, staff=self.lecturer, package=self.package,
                                   contact_proportion=100, assessment_proportion=100, admin_proportion=100)
        self.login(self.admin)
        self.confirm([(self.coordinator, 10, 0, 0)])
        self.assertTrue(ModuleStaff.objects.filter(module=other, staff=self.lecturer).exists())
