"""Tests for directory integration: staff records, the onboard_staff command and the Graph source"""
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .directory import DirectorySource, apply_staff_record, onboard_staff_record
from .directory_graph import GraphDirectorySource, get_path, odata_string
from .models import Campus, Faculty, School, Staff

RECORDS = [
    {'username': 'E00001', 'first_name': 'Ann', 'last_name': 'Lecturer', 'email': 'a.lecturer@example.ac.uk',
     'job_title': 'Lecturer', 'school': 'School of Computing', 'faculty': 'Faculty of Computing',
     'campus': 'Belfast', 'is_external': False},
    {'username': 'A00009', 'first_name': 'Xav', 'last_name': 'Examiner', 'email': 'x.examiner@example.ac.uk',
     'school': 'School of Computing', 'faculty': 'Faculty of Computing', 'is_external': True},
]


class FakeDirectorySource(DirectorySource):
    def staff_in_school(self, school):
        return [dict(r) for r in RECORDS if r['school'] == school]


FAKE_SOURCE = 'loads.tests_directory.FakeDirectorySource'


class StaffRecordTestCase(TestCase):

    def test_onboard_creates_user_and_staff(self):
        staff, created = onboard_staff_record(dict(RECORDS[0]))
        self.assertTrue(created)
        user = staff.user
        self.assertEqual(user.username, 'E00001')
        self.assertEqual(user.email, 'a.lecturer@example.ac.uk')
        self.assertFalse(user.has_usable_password())
        self.assertEqual(staff.staff_number, 'E00001')
        self.assertEqual(staff.job_title, 'Lecturer')
        self.assertEqual(staff.school.system_name, 'School of Computing')
        self.assertEqual(staff.school.faculty, staff.faculty)
        self.assertEqual(staff.campus.system_name, 'Belfast')
        self.assertFalse(staff.is_external)
        self.assertIn('School of Computing Staff', [g.name for g in user.groups.all()])

    def test_onboard_external(self):
        staff, created = onboard_staff_record(dict(RECORDS[1]))
        self.assertTrue(staff.is_external)
        self.assertEqual([g.name for g in staff.user.groups.all()], ['School of Computing External Examiners'])

    def test_onboard_is_idempotent_and_case_insensitive(self):
        onboard_staff_record(dict(RECORDS[0]))
        record = dict(RECORDS[0], username='e00001', job_title='Senior Lecturer')
        staff, created = onboard_staff_record(record)
        self.assertFalse(created)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Staff.objects.count(), 1)
        self.assertEqual(staff.job_title, 'Senior Lecturer')

    def test_missing_fields_are_left_alone(self):
        staff, created = onboard_staff_record(dict(RECORDS[0]))
        staff = apply_staff_record(staff.user, {'username': 'E00001', 'job_title': 'Reader'})
        self.assertEqual(staff.job_title, 'Reader')
        self.assertEqual(staff.campus.system_name, 'Belfast')
        self.assertEqual(staff.user.first_name, 'Ann')

    def test_staff_number_can_differ_from_username(self):
        staff, created = onboard_staff_record({'username': 'ann@example.ac.uk', 'staff_number': 'E00001'})
        self.assertEqual(staff.staff_number, 'E00001')

    def test_username_required(self):
        with self.assertRaises(ValueError):
            onboard_staff_record({'first_name': 'Nobody'})


@override_settings(WAM_DIRECTORY_SOURCE=FAKE_SOURCE)
class OnboardStaffCommandTestCase(TestCase):

    def run_command(self, *args):
        out = StringIO()
        call_command('onboard_staff', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        output = self.run_command('School of Computing', '--dry-run')
        self.assertIn('[dry-run] create staff', output)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(School.objects.count(), 0)

    def test_onboard(self):
        output = self.run_command('School of Computing')
        self.assertIn('2 created, 0 updated, 0 skipped', output)
        self.assertEqual(Staff.objects.filter(is_external=True).count(), 1)
        output = self.run_command('School of Computing')
        self.assertIn('0 created, 2 updated', output)
        self.assertEqual(User.objects.count(), 2)

    def test_no_externals(self):
        output = self.run_command('School of Computing', '--no-externals')
        self.assertIn('1 created, 0 updated, 1 skipped', output)

    def test_unknown_school(self):
        output = self.run_command('School of Nothing')
        self.assertIn('0 created', output)

    @override_settings(WAM_DIRECTORY_SOURCE=None)
    def test_not_configured(self):
        with self.assertRaises(CommandError):
            self.run_command('School of Computing')


class FakeResponse:
    def __init__(self, data, status_code=200):
        self.data, self.status_code = data, status_code

    def json(self):
        return self.data

    def raise_for_status(self):
        pass


GRAPH_USERS = [
    {'userPrincipalName': 'a.lecturer@example.ac.uk', 'givenName': 'Ann', 'surname': 'Lecturer',
     'mail': 'a.lecturer@example.ac.uk', 'jobTitle': 'Lecturer', 'department': 'School of Computing',
     'companyName': 'Faculty of Computing', 'officeLocation': 'Belfast',
     'onPremisesExtensionAttributes': {'extensionAttribute1': 'E00001'}},
    {'userPrincipalName': 'b.lecturer@example.ac.uk', 'givenName': 'Bob', 'surname': 'Lecturer',
     'department': 'School of Computing', 'onPremisesExtensionAttributes': None},
]


class GraphDirectorySourceTestCase(TestCase):

    def test_get_path(self):
        self.assertEqual(get_path(GRAPH_USERS[0], 'onPremisesExtensionAttributes.extensionAttribute1'), 'E00001')
        self.assertIsNone(get_path(GRAPH_USERS[1], 'onPremisesExtensionAttributes.extensionAttribute1'))
        self.assertIsNone(get_path(GRAPH_USERS[0], 'nothing.here'))

    def test_filter_escaping(self):
        self.assertEqual(odata_string("St Mary's"), "'St Mary''s'")
        with override_settings(WAM_GRAPH_FILTER="employeeType eq 'Staff'"):
            source = GraphDirectorySource()
        self.assertEqual(source.build_filter("St Mary's"),
                         "department eq 'St Mary''s' and accountEnabled eq true and (employeeType eq 'Staff')")

    @override_settings(WAM_GRAPH_ATTRIBUTE_MAP={
        'username': 'onPremisesExtensionAttributes.extensionAttribute1', 'first_name': 'givenName'})
    def test_custom_attribute_map(self):
        source = GraphDirectorySource()
        self.assertEqual(source.select_attributes(), ['givenName', 'onPremisesExtensionAttributes'])
        self.assertEqual(source.to_record(GRAPH_USERS[0]), {'username': 'E00001', 'first_name': 'Ann'})

    def test_paging_and_mapping(self):
        pages = [
            FakeResponse({'value': GRAPH_USERS[:1], '@odata.nextLink': 'https://graph.example/next'}),
            FakeResponse({'value': GRAPH_USERS[1:]}),
        ]
        source = GraphDirectorySource()
        source._token = 'token'
        with mock.patch('requests.get', side_effect=pages) as get:
            records = list(source.staff_in_school('School of Computing'))

        self.assertEqual([r['username'] for r in records],
                         ['a.lecturer@example.ac.uk', 'b.lecturer@example.ac.uk'])
        self.assertEqual(records[0]['campus'], 'Belfast')
        first, second = get.call_args_list
        self.assertEqual(first.kwargs['headers']['ConsistencyLevel'], 'eventual')
        self.assertIn("department eq 'School of Computing'", first.kwargs['params']['$filter'])
        self.assertEqual(second.args[0], 'https://graph.example/next')
        self.assertIsNone(second.kwargs['params'])

    def test_subclass_can_skip_users(self):
        class StaffOnly(GraphDirectorySource):
            def to_record(self, graph_user):
                if not graph_user.get('mail'):
                    return None
                return super().to_record(graph_user)

        source = StaffOnly()
        with mock.patch.object(source, 'graph_users', return_value=GRAPH_USERS):
            records = list(source.staff_in_school('School of Computing'))
        self.assertEqual(len(records), 1)

    @override_settings(WAM_GRAPH_CLIENT_ID=None)
    def test_missing_credentials(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaises(ImproperlyConfigured):
            GraphDirectorySource().get_token()
