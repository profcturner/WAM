"""Tests for workload calculations: semesters, formulas, activities, modules, staff totals and generators"""
import datetime
import logging
import unittest

from django.core.exceptions import ValidationError
from django.test import TestCase

from .formula_engine import (FormulaError, calculate_admin_hours, calculate_all_hours,
                             calculate_assessment_hours, calculate_contact_hours,
                             calculate_coordinator_hours)
from .helpers import divide_by_semesters
from .models import Activity, ActivityGenerator, Body, Project, ProjectStaff
from .testing import allocate, make_activity_type, make_group, make_module, make_package, make_staff
from .validators import validate_formula


class DivideBySemestersTestCase(unittest.TestCase):

    def test_single_semester(self):
        self.assertEqual(divide_by_semesters(30, '2'), [30, 0, 30, 0])

    def test_split_evenly(self):
        self.assertEqual(divide_by_semesters(30, '1,2,3'), [30, 10, 10, 10])
        self.assertEqual(divide_by_semesters(30, '1,3'), [30, 15, 0, 15])

    def test_spaces_are_ignored(self):
        self.assertEqual(divide_by_semesters(30, '1, 3'), [30, 15, 0, 15])

    def test_zero_hours(self):
        self.assertEqual(divide_by_semesters(0, '1,2'), [0, 0, 0, 0])


class FakePackage:
    """Stands in for a WorkPackage, which is all the formula engine reads"""

    def __init__(self, **kwargs):
        self.credit_contact_scaling = 2.5
        self.contact_admin_scaling = 1.0
        self.contact_assessment_scaling = 0.5
        self.contact_formula = self.admin_formula = self.assessment_formula = self.coordinator_formula = ''
        self.__dict__.update(kwargs)


class FormulaEngineTestCase(unittest.TestCase):

    def test_legacy_scalar_fallbacks(self):
        package = FakePackage()
        self.assertEqual(calculate_contact_hours(package, 20, 100), 50)
        self.assertEqual(calculate_admin_hours(package, 20, 100, contact=50), 50)
        self.assertEqual(calculate_assessment_hours(package, 20, 100, contact=50, admin=50), 25)
        self.assertEqual(calculate_coordinator_hours(package, 20, 100), 0)

    def test_formulas(self):
        package = FakePackage(contact_formula='credits * contact_scaling + students / 10',
                              admin_formula='contact * admin_scaling + 5',
                              assessment_formula='admin + sqrt(students)',
                              coordinator_formula='max(10, students / 5)')
        self.assertEqual(calculate_contact_hours(package, 20, 100), 60)
        self.assertEqual(calculate_coordinator_hours(package, 20, 100), 20)
        self.assertEqual(calculate_coordinator_hours(package, 20, 10), 10)

    def test_all_hours_chains_results(self):
        """Admin uses the calculated contact hours, and assessment uses both"""
        package = FakePackage(contact_formula='credits', admin_formula='contact * 2',
                              assessment_formula='contact + admin')
        self.assertEqual(calculate_all_hours(package, 20, 100),
                         {'contact': 20, 'admin': 40, 'assessment': 60})

    def test_results_are_floats(self):
        self.assertIsInstance(calculate_contact_hours(FakePackage(contact_formula='credits'), 20, 1), float)

    def test_unknown_variable(self):
        # Contact hours are not known when contact hours are being calculated
        with self.assertRaises(FormulaError):
            calculate_contact_hours(FakePackage(contact_formula='contact * 2'), 20, 100)

    def test_division_by_zero(self):
        with self.assertRaises(FormulaError):
            calculate_contact_hours(FakePackage(contact_formula='credits / (students - 100)'), 20, 100)

    @unittest.expectedFailure
    def test_syntax_error(self):
        """BUG: a malformed formula raises a bare SyntaxError rather than FormulaError"""
        with self.assertRaises(FormulaError):
            calculate_contact_hours(FakePackage(contact_formula='credits *'), 20, 100)

    def test_disallowed_function(self):
        with self.assertRaises(FormulaError):
            calculate_contact_hours(FakePackage(contact_formula="__import__('os')"), 20, 100)

    @unittest.expectedFailure
    def test_math_domain_error_is_a_formula_error(self):
        """BUG: log(0) raises a bare ValueError rather than FormulaError, so callers can't catch it cleanly"""
        with self.assertRaises(FormulaError):
            calculate_contact_hours(FakePackage(contact_formula='log(students)'), 20, 0)


class ValidateFormulaTestCase(unittest.TestCase):

    def assertInvalid(self, formula):
        with self.assertRaises(ValidationError, msg=formula):
            validate_formula(formula)

    def test_empty_is_valid(self):
        validate_formula('')
        validate_formula(None)

    def test_valid_formulas(self):
        for formula in ('credits * contact_scaling', 'log(students) * 10', 'round(contact / 3, 1)',
                        'max(admin, 5) + min(credits, 40)'):
            validate_formula(formula)

    def test_invalid_formulas(self):
        self.assertInvalid('credits *')
        self.assertInvalid('lecturers * 2')
        self.assertInvalid("open('/etc/passwd')")
        self.assertInvalid("'a string'")

    def test_division_by_zero_with_dummy_values_is_allowed(self):
        # The dummy values might divide by zero where real data won't
        validate_formula('credits / (students - 100)')


class HoursTestCase(TestCase):
    """Activity and Module hours"""

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.package = make_package(nominal_hours=1600)
        self.activity_type = make_activity_type()

    def make_activity(self, **kwargs):
        defaults = dict(name="Activity", hours=0, percentage=0, activity_type=self.activity_type,
                        package=self.package, semester='1,2')
        defaults.update(kwargs)
        return Activity.objects.create(**defaults)

    def test_activity_in_hours(self):
        activity = self.make_activity(hours=30, hours_percentage=Activity.HOURS)
        self.assertEqual(activity.total_hours(), 30)
        self.assertEqual(activity.hours_by_semester(), [30, 15, 15, 0])

    def test_activity_as_percentage(self):
        activity = self.make_activity(percentage=10, hours_percentage=Activity.PERCENTAGE)
        self.assertEqual(activity.total_hours(), 160)

    def test_module_overrides(self):
        module = make_module(self.package, semester='1,2', contact_hours=12, admin_hours=3,
                             assessment_hours=6)
        self.assertEqual(module.get_contact_hours(), 12)
        self.assertEqual(module.get_admin_hours(), 3)
        self.assertEqual(module.get_assessment_hours(), 6)
        self.assertEqual(module.get_contact_hours_by_semester(), [12, 6, 6, 0])

    def test_module_formula_respects_contact_override(self):
        """Admin and assessment are calculated from the overridden contact hours"""
        self.package.contact_admin_scaling = 0.5
        self.package.contact_assessment_scaling = 2
        self.package.save()
        module = make_module(self.package, contact_hours=10)
        self.assertEqual(module.get_admin_hours(), 5)
        self.assertEqual(module.get_assessment_hours(), 20)

    def test_module_default_contact(self):
        module = make_module(self.package, credits=20)
        self.assertEqual(module.get_contact_hours(), 50)  # 20 credits * 2.5 default scaling

    def test_coordinator_hours(self):
        module = make_module(self.package, coordinator_hours=8)
        self.assertEqual(module.get_coordinator_hours(), 0, "no coordinator, no hours")
        module.coordinator = make_staff('coordinator')
        self.assertEqual(module.get_coordinator_hours(), 8)

        module.coordinator_hours = None
        self.package.coordinator_formula = 'students / 10'
        self.package.save()
        self.assertEqual(module.get_coordinator_hours(), 10)


class StaffTotalsTestCase(TestCase):
    """Staff.hours_by_semester and hours_by_category, which drive the loads pages and charts"""

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.package = make_package(nominal_hours=1600)
        self.lecturing = make_activity_type("Lecturing", "Education")
        self.admin_type = make_activity_type("Admin", "Administration")
        self.staff = make_staff('lecturer', package=self.package)

        # 40 hours over semesters 1 and 2
        Activity.objects.create(name="Duties", hours=40, percentage=0, semester='1,2',
                                activity_type=self.lecturing, package=self.package, staff=self.staff)
        # A module in semester 1 with 20 contact, 10 admin and 10 assessment hours,
        # of which this member of staff does half of each
        self.module = make_module(self.package, semester='1', contact_hours=20, admin_hours=10,
                                  assessment_hours=10)
        allocation = allocate(self.staff, self.module, contact=50, admin=50, assessment=50)
        allocation.activity_type = self.lecturing
        allocation.save()

    def test_hours_by_semester(self):
        total, s1, s2, s3, activity_count = self.staff.hours_by_semester(self.package)
        self.assertEqual((s1, s2, s3), (20 + 20, 20, 0))
        self.assertEqual(total, 60)
        self.assertEqual(activity_count, 1)
        self.assertEqual(self.staff.total_hours(self.package), 60)

    def test_coordinator_hours_are_included(self):
        self.module.coordinator = self.staff
        self.module.coordinator_hours = 6
        self.module.save()
        self.assertEqual(self.staff.total_hours(self.package), 66)

    def test_other_packages_are_ignored(self):
        other = make_package("Other")
        Activity.objects.create(name="Elsewhere", hours=100, percentage=0, activity_type=self.lecturing,
                                package=other, staff=self.staff)
        self.assertEqual(self.staff.total_hours(self.package), 60)

    def test_category_totals_match_semester_totals(self):
        self.module.coordinator = self.staff
        self.module.coordinator_hours = 6
        self.module.save()
        self.package.coordinator_activity_type = self.admin_type
        self.package.save()

        by_category = self.staff.hours_by_category(self.package)
        self.assertEqual(by_category[self.lecturing.category], 60)
        self.assertEqual(by_category[self.admin_type.category], 6)
        self.assertAlmostEqual(sum(by_category.values()), self.staff.total_hours(self.package))


class GeneratorTestCase(TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.group = make_group()
        self.package = make_package(group=self.group, working_days=228, days_in_week=5)
        self.activity_type = make_activity_type()
        self.lecturer = make_staff('lecturer', group=self.group, package=self.package)
        self.other = make_staff('other', package=self.package)

    def make_generator(self):
        generator = ActivityGenerator.objects.create(
            name="Open day", hours=5, percentage=0, semester='1', activity_type=self.activity_type,
            package=self.package, details="")
        generator.groups.add(self.group)
        generator.targets.add(self.other)
        return generator

    def test_targets_by_user_and_group(self):
        generator = self.make_generator()
        generator.targets.add(self.lecturer)  # also in the group, but only counted once
        self.assertCountEqual(generator.get_all_targets(), [self.lecturer, self.other])

    def test_generate_activities(self):
        self.make_generator().generate_activities()
        self.assertEqual(Activity.objects.filter(name="Open day").count(), 2)
        self.assertEqual(self.lecturer.total_hours(self.package), 5)

    @unittest.expectedFailure
    def test_regenerating_replaces_activities(self):
        """BUG: regenerating doesn't remove the previous activities, so every regeneration adds load again"""
        generator = self.make_generator()
        generator.generate_activities()
        generator.generate_activities()
        self.assertEqual(self.lecturer.total_hours(self.package), 5)

    def test_project_activities(self):
        """Hours are hours per week, over the working weeks of the overlap with each package"""
        body = Body.objects.create(name="Research Council", details="")
        project = Project.objects.create(name="Grant", body=body, activity_type=self.activity_type,
                                         start=datetime.date(2017, 1, 1), end=datetime.date(2019, 1, 1))
        # Covers the whole package: 228 working days, so 45.6 weeks.
        # (Activity.hours is an integer field, so fractional hours are truncated)
        ProjectStaff.objects.create(staff=self.lecturer, project=project, hours_per_week=5,
                                    start=self.package.startdate, end=self.package.enddate)

        project.generate_activities()
        self.assertEqual(self.lecturer.total_hours(self.package), 228)

        # Regenerating replaces rather than adds
        project.generate_activities()
        self.assertEqual(self.lecturer.total_hours(self.package), 228)

    def test_project_partly_in_package(self):
        body = Body.objects.create(name="Research Council", details="")
        project = Project.objects.create(name="Grant", body=body, activity_type=self.activity_type,
                                         start=datetime.date(2018, 3, 2), end=datetime.date(2019, 1, 1))
        # 182 of the package's 364 days, so half the working weeks: 22.8
        ProjectStaff.objects.create(staff=self.lecturer, project=project, hours_per_week=10,
                                    start=project.start, end=project.end)
        project.generate_activities()
        self.assertEqual(self.lecturer.total_hours(self.package), 228)

    def test_project_outside_package(self):
        body = Body.objects.create(name="Research Council", details="")
        project = Project.objects.create(name="Old grant", body=body, activity_type=self.activity_type,
                                         start=datetime.date(2010, 1, 1), end=datetime.date(2011, 1, 1))
        ProjectStaff.objects.create(staff=self.lecturer, project=project, hours_per_week=2,
                                    start=project.start, end=project.end)
        project.generate_activities()
        self.assertEqual(self.lecturer.total_hours(self.package), 0)
