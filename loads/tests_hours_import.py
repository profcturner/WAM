"""Tests for importing hours per person for many modules from a spreadsheet"""
import io
import json
from decimal import Decimal as D

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import reverse

from WAM.settings import WAM_DEFAULT_ACTIVITY_TYPE

from .hours_import import HoursImport, PeopleIndex, find_columns, parse_hours, read_cells
from .models import ActivityType, Category, Module, ModuleStaff, Staff
from .testing import make_module, make_staff
from .tests_views import ViewTestCase

PERMISSIONS = ['loads.change_module', 'loads.add_modulestaff', 'loads.change_modulestaff',
               'loads.delete_modulestaff']


class ReadingTests(SimpleTestCase):

    def test_pasted_cells_with_row_numbers(self):
        rows = read_cells(text="Module\tStaff\tContact\n\nCOM101\tAnn Lee\t12\n")
        self.assertEqual(rows, [(1, ['Module', 'Staff', 'Contact']), (3, ['COM101', 'Ann Lee', '12'])])

    def test_csv(self):
        self.assertEqual(read_cells(text='COM101,"Lee, Ann",12,7.5,0'), [(1, ['COM101', 'Lee, Ann', '12', '7.5', '0'])])

    def test_upload_types(self):
        csv = SimpleUploadedFile('hours.csv', b'\xef\xbb\xbfCOM101,Ann Lee,12\r\n')
        self.assertEqual(read_cells(upload=csv), [(1, ['COM101', 'Ann Lee', '12'])])
        with self.assertRaisesMessage(Exception, "Please upload a .xlsx or .csv file"):
            read_cells(upload=SimpleUploadedFile('hours.pdf', b'%PDF'))
        with self.assertRaisesMessage(Exception, "doesn't look like an Excel"):
            read_cells(upload=SimpleUploadedFile('hours.xlsx', b'not really'))

    def test_xlsx(self):
        import openpyxl
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(["Module code", "Staff member", "Contact hours", "Assessment hours", "Admin hours"])
        sheet.append(["COM101", "Ann Lee", 12, 7.5, None])
        data = io.BytesIO()
        workbook.save(data)
        rows = read_cells(upload=SimpleUploadedFile('hours.xlsx', data.getvalue()))
        self.assertEqual(rows[1], (2, ['COM101', 'Ann Lee', '12', '7.5', '']))

    def test_columns_by_header_in_any_order(self):
        columns, header = find_columns([(1, ['Admin hours', 'Module name', 'Module code', 'Lecturer', 'Contact'])])
        self.assertTrue(header)
        self.assertEqual(columns, {'admin': 0, 'module': 2, 'person': 3, 'contact': 4})

    def test_columns_without_a_header(self):
        columns, header = find_columns([(1, ['COM101', 'Ann Lee', '12', '7', '0'])])
        self.assertFalse(header)
        self.assertEqual(columns, {'module': 0, 'person': 1, 'contact': 2, 'assessment': 3, 'admin': 4})

    def test_hours(self):
        self.assertEqual([parse_hours(c) for c in ('', '-', '7.5', '7,5', '12h', '3 hours', '0')],
                         [0, 0, D('7.5'), D('7.5'), 12, 3, 0])
        for bad in ('-2', 'lots', 'NaN', 'Infinity'):
            self.assertIsNone(parse_hours(bad), bad)


class ImportTestCase(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.admin = make_staff('schooladmin', group=self.group, permissions=PERMISSIONS)
        self.admin.package = self.package  # their current work package
        self.admin.save()
        self.other_module = make_module(self.other_package, code="OTH100")
        for staff, first, last, number in ((self.lecturer, "Ann", "Lee", "E001"),
                                           (self.coordinator, "Ben", "Hart", "E002")):
            staff.user.first_name, staff.user.last_name, staff.user.email = first, last, f"{first.lower()}@example.ac.uk"
            staff.user.save()
            staff.staff_number = number
            staff.save()
        self.second = make_module(self.package, code="COM202")
        category = Category.objects.create(name="Education", abbreviation="edu", colour="red")
        ActivityType.objects.get_or_create(pk=WAM_DEFAULT_ACTIVITY_TYPE,
                                           defaults={'name': "Module teaching", 'category': category})
        self.url = reverse('module_hours_import')

    def importer(self, text, may_change=lambda module: True):
        staff = Staff.objects.filter(pk__in=self.package.get_all_staff().values_list('pk', flat=True),
                                     is_external=False)
        return HoursImport(read_cells(text=text), self.package, staff, may_change)


class PeopleTests(ImportTestCase):

    def test_ways_of_naming_people(self):
        index = PeopleIndex(Staff.objects.all())
        for text in ("Ann Lee", "ann  lee", "Lee, Ann", "Lee Ann", "Dr Ann Lee", "Dr. Ann Lee", "A. Lee", "A Lee",
                     "Lee, A.", "Dr A.Lee", "ann@example.ac.uk",
                     self.lecturer.user.username, "E001"):
            self.assertEqual(index.find(text), (self.lecturer, None), text)

    def test_unknown_and_ambiguous(self):
        make_staff('alan', group=self.group, first_name="Alan", last_name="Lee")
        self.assertIn("matches more than one person", PeopleIndex(Staff.objects.all()).find("A. Lee")[1])
        twin = make_staff('twin', group=self.group, first_name="Ann", last_name="Lee")
        index = PeopleIndex(Staff.objects.all())
        self.assertIn("matches more than one person", index.find("Ann Lee")[1])
        self.assertEqual(index.find("twin")[0], twin)
        self.assertIn("No staff member", index.find("Nobody Here")[1])
        self.assertIn("No staff member given", index.find("")[1])


class HoursImportTests(ImportTestCase):

    def test_plans_per_module(self):
        result = self.importer(f"Module\tStaff\tContact\tAssessment\tAdmin\n"
                               f"{self.module.module_code}\tAnn Lee\t12\t7.5\t\n"
                               f"{self.module.module_code}\tBen Hart\t50\t7.5\t4\n"
                               f"COM202\tLee, Ann\t30\t0\t0\n")
        self.assertTrue(result.has_header)
        self.assertEqual([item.module for item in result.ready], [self.module, self.second])
        plan = result.ready[0].plan
        self.assertEqual(plan.totals, {'contact': 62, 'assessment': 15, 'admin': 4})
        self.assertEqual([p['contact'] for p in plan.people], [D('19.35'), D('80.65')])
        self.assertEqual(result.problem_rows, [])

    def test_problems_leave_out_the_module(self):
        result = self.importer(f"{self.module.module_code}\tAnn Lee\t12\t0\t0\n"
                               f"{self.module.module_code}\tNo One\t5\t0\t0\n"
                               "COM202\tAnn Lee\tlots\t0\t0\n"
                               "XYZ999\tAnn Lee\t1\t0\t0\n")
        self.assertEqual(result.ready, [])
        self.assertEqual([item.module for item in result.skipped], [self.module, self.second])
        self.assertEqual([row.line for row in result.problem_rows], [2, 3, 4])
        self.assertEqual([row.module_text for row in result.unmatched], ['XYZ999'])

    def test_someone_twice_on_a_module(self):
        result = self.importer(f"{self.module.module_code}\tAnn Lee\t12\t0\t0\n"
                               f"{self.module.module_code}\tLee, Ann\t5\t0\t0\n")
        self.assertIn("more than once", result.problem_rows[0].problems[0])
        self.assertEqual(result.ready, [])

    def test_module_they_may_not_change(self):
        result = self.importer(f"{self.module.module_code}\tAnn Lee\t12\t0\t0\nCOM202\tAnn Lee\t5\t0\t0\n",
                               may_change=lambda module: module != self.module)
        self.assertEqual([item.module for item in result.ready], [self.second])
        self.assertIn("permission", result.skipped[0].problems[0])

    def test_duplicate_module_codes(self):
        make_module(self.package, code="COM202", semester="2")
        result = self.importer("COM202\tAnn Lee\t5\t0\t0\n")
        self.assertIn("more than one module", result.unmatched[0].problems[0])

    def test_no_hours_for_anyone(self):
        result = self.importer("COM202\tAnn Lee\t0\t0\t0\n")
        self.assertEqual(result.skipped[0].problems, ["No hours are given for anyone."])


class ImportPageTests(ImportTestCase):

    def check(self, text):
        self.login(self.admin)
        return self.client.post(self.url, {'pasted': text, 'check': '1'})

    def confirm(self, response, **changes):
        result = response.context['result']
        data = {'confirm': '1', 'payload': result.payload(), 'fingerprint': result.fingerprint()}
        data.update(changes)
        return self.client.post(self.url, data)

    def test_who_can_use_it(self):
        self.superuser.package = self.package
        self.superuser.save()
        for staff, status in ((self.admin, 200), (self.superuser, 200)):
            self.login(staff)
            self.assertEqual(self.client.get(self.url).status_code, status)
        for staff in (self.lecturer, make_staff('partial', group=self.group, permissions=PERMISSIONS[1:])):
            self.login(staff)
            self.assertRedirects(self.client.get(self.url), reverse('forbidden'), fetch_redirect_response=False)
            self.assertRedirects(self.client.post(self.url, {'pasted': 'x'}), reverse('forbidden'),
                                 fetch_redirect_response=False)

    def test_admin_menu_link(self):
        self.login(self.superuser)
        self.assertContains(self.client.get(reverse('custom_admin_index')), self.url)

    def test_preview_then_confirm(self):
        ModuleStaff.objects.create(module=self.second, staff=self.coordinator, package=self.package,
                                   contact_proportion=100, assessment_proportion=100, admin_proportion=100)
        untouched = make_module(self.package, code="COM303")
        response = self.check(f"{self.module.module_code}\tAnn Lee\t12\t7.5\t0\n"
                              f"{self.module.module_code}\tben hart\t50\t7.5\t4\n"
                              "COM202\tE001\t30\t10\t2\n"
                              "COM404\tAnn Lee\t1\t1\t1\n")
        self.assertContains(response, "Ready to save")
        self.assertContains(response, "No module")
        self.assertFalse(ModuleStaff.objects.filter(module=self.module).exists())  # nothing saved yet

        response = self.confirm(response)
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.module.refresh_from_db()
        self.assertEqual((self.module.contact_hours, self.module.assessment_hours), (62, 15))
        self.assertEqual(ModuleStaff.objects.get(module=self.module, staff=self.lecturer).contact_proportion, D('19.35'))
        self.assertEqual(list(ModuleStaff.objects.filter(module=self.second).values_list('staff', 'contact_proportion')),
                         [(self.lecturer.pk, 100)])  # replaced
        self.assertIsNone(Module.objects.get(pk=untouched.pk).contact_hours)

    def test_tampering_is_refused(self):
        response = self.check(f"{self.module.module_code}\tAnn Lee\t12\t0\t0\n")
        payload = json.loads(response.context['result'].payload())
        for bad in ([[self.module.pk, [[self.outsider.pk, "12", "0", "0"]]]],     # someone outside the package
                    [[self.other_module.pk, [[self.lecturer.pk, "12", "0", "0"]]]],  # another package's module
                    [[self.module.pk, [[self.lecturer.pk, "-5", "0", "0"]]]],
                    "not json"):
            data = json.dumps(bad) if not isinstance(bad, str) else bad
            self.client.post(self.url, {'confirm': '1', 'payload': data,
                                        'fingerprint': response.context['result'].fingerprint()})
        # Changed figures, even with a matching shape, don't match the preview's fingerprint
        payload[0][1][0][1] = "99"
        self.client.post(self.url, {'confirm': '1', 'payload': json.dumps(payload),
                                    'fingerprint': response.context['result'].fingerprint()})
        self.assertFalse(ModuleStaff.objects.exists())

    def test_nothing_to_import(self):
        self.assertContains(self.check("  \n"), "nothing to import")

    def test_upload(self):
        self.login(self.admin)
        upload = SimpleUploadedFile('hours.csv', f"{self.module.module_code},Ann Lee,10,0,0\n".encode())
        response = self.client.post(self.url, {'pasted': '', 'upload': upload, 'check': '1'})
        self.assertEqual(len(response.context['result'].ready), 1)
