"""Tests for form validation: account creation and work package migration"""
import logging
import unittest
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from .forms import ExternalExaminerCreationForm, MigrateWorkPackageForm, StaffCreationForm
from .models import Staff
from .testing import make_group, make_package, make_staff


def account_data(**kwargs):
    data = dict(username='newuser', email='new.user@example.ac.uk', title='Dr', first_name='New',
                last_name='User', password1='', password2='', staff_number='')
    data.update(kwargs)
    return data


class StaffCreationFormTestCase(TestCase):
    form_class = StaffCreationForm

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.package = make_package()

    def form(self, **kwargs):
        return self.form_class(data=account_data(**kwargs))

    def assertFieldError(self, field, **kwargs):
        form = self.form(**kwargs)
        self.assertFalse(form.is_valid())
        self.assertIn(field, form.errors)

    def test_creates_user_and_staff(self):
        group = make_group()
        form = self.form(username='NewUser', package=self.package.pk, groups=[group.pk])
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        self.assertEqual(user.username, 'newuser', "usernames are lower cased")
        self.assertFalse(user.has_usable_password(), "no password means external authentication only")
        self.assertIn(group, user.groups.all())
        staff = Staff.objects.get(user=user)
        self.assertEqual(staff.staff_number, 'newuser', "staff number falls back to the username")
        self.assertEqual(staff.title, 'Dr')
        self.assertEqual(staff.package, self.package)
        self.assertFalse(staff.is_external)

    def test_explicit_staff_number(self):
        form = self.form(staff_number='E12345')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(Staff.objects.get(user=form.save()).staff_number, 'e12345')

    def test_duplicate_username(self):
        make_staff('existing')
        self.assertFieldError('username', username='Existing')

    def test_short_username(self):
        self.assertFieldError('username', username='abc')

    def test_duplicate_email(self):
        make_staff('existing')
        self.assertFieldError('email', email='EXISTING@example.ac.uk')

    def test_duplicate_staff_number(self):
        staff = make_staff('existing')
        staff.staff_number = 'e12345'
        staff.save()
        self.assertFieldError('staff_number', staff_number='E12345')

    def test_mismatched_passwords(self):
        self.assertFieldError('password2', password1='secret-one', password2='secret-two')

    @unittest.expectedFailure
    def test_password_confirmation_required(self):
        """BUG: a password with an empty confirmation is accepted"""
        self.assertFieldError('password2', password1='secret-one', password2='')

    @unittest.expectedFailure
    def test_creates_user_with_password(self):
        """BUG: save() reads self.password1, which doesn't exist, so supplying a password crashes"""
        form = self.form(password1='a-good-secret', password2='a-good-secret')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save().check_password('a-good-secret'))

    def test_staff_regex(self):
        with mock.patch('loads.forms.WAM_STAFF_REGEX', r'e\d+'):
            self.assertFieldError('username', username='student1')
            self.assertTrue(self.form(username='e1234').is_valid())


class ExternalExaminerCreationFormTestCase(StaffCreationFormTestCase):
    form_class = ExternalExaminerCreationForm

    def test_creates_user_and_staff(self):
        form = self.form(package=self.package.pk)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertFalse(user.has_usable_password())
        self.assertTrue(Staff.objects.get(user=user).is_external)

    def test_staff_regex(self):
        with mock.patch('loads.forms.WAM_STAFF_REGEX', r'e\d+'), \
                mock.patch('loads.forms.WAM_EXTERNAL_REGEX', r'x\d+'):
            self.assertFieldError('username', username='e1234')
            self.assertTrue(self.form(username='x1234').is_valid())

    @unittest.expectedFailure
    def test_external_regex_alone(self):
        """BUG: the external regex is only applied if WAM_STAFF_REGEX is set, and crashes if only that is"""
        with mock.patch('loads.forms.WAM_EXTERNAL_REGEX', r'x\d+'):
            self.assertFieldError('username', username='e1234')

    @unittest.expectedFailure
    def test_staff_regex_alone(self):
        """BUG: with only WAM_STAFF_REGEX set, re.match(None, ...) raises TypeError"""
        with mock.patch('loads.forms.WAM_STAFF_REGEX', r'e\d+'):
            self.assertTrue(self.form(username='x1234').is_valid())


class MigrateWorkPackageFormTestCase(TestCase):

    def setUp(self):
        self.source = make_package("2017/18")
        self.destination = make_package("2018/19")

    def form(self, **kwargs):
        data = dict(source_package=self.source.pk, destination_package=self.destination.pk,
                    copy_programmes=True, copy_modules=True, copy_modulestaff=True,
                    copy_activities_modules=True, copy_activities_generated=True,
                    copy_activities_custom=True, generate_projects=True)
        data.update(kwargs)
        # Unticked checkboxes are absent from POST data
        return MigrateWorkPackageForm(data={k: v for k, v in data.items() if v is not False})

    def test_valid(self):
        self.assertTrue(self.form().is_valid())

    def test_same_package(self):
        form = self.form(destination_package=self.source.pk)
        self.assertFalse(form.is_valid())
        self.assertIn('destination_package', form.errors)

    def test_missing_packages(self):
        form = self.form(source_package='', destination_package='')
        self.assertFalse(form.is_valid())
        self.assertIn('source_package', form.errors)
        self.assertIn('destination_package', form.errors)

    def test_dependencies(self):
        """Modules need programmes; allocations and module activities need modules"""
        self.assertIn('copy_modules', self.form(copy_programmes=False).errors)
        no_modules = self.form(copy_modules=False)
        self.assertIn('copy_modulestaff', no_modules.errors)
        self.assertIn('copy_activities_modules', no_modules.errors)
        self.assertTrue(self.form(copy_modules=False, copy_modulestaff=False,
                                  copy_activities_modules=False).is_valid())
