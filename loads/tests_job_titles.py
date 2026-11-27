"""Tests for suggesting what kind of staff someone is from their job title"""
import io

from django.contrib.admin.models import LogEntry
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from .directory import onboard_staff_record
from .job_titles import ACADEMIC, OTHER, RESEARCH, Suggestion, apply_suggestion, classify
from .models import School, Staff
from .tests_school_groups import SchoolGroupsTestCase


class ClassifyTests(SimpleTestCase):

    def test_titles(self):
        for title, kind in (
                ("Lecturer", ACADEMIC), ("Senior Lecturer", ACADEMIC), ("Reader in Pharmacology", ACADEMIC),
                ("Professor", ACADEMIC), ("Assistant Professor", ACADEMIC), ("Visiting Professor", ACADEMIC),
                ("Teaching Fellow", ACADEMIC), ("Head of School of Nursing", ACADEMIC),
                ("Dean of the Faculty of Life and Health Sciences", ACADEMIC),
                ("Senior Lecturer in Business Administration", ACADEMIC),  # the subject doesn't count
                ("Professor of Health Management", ACADEMIC), ("LECTURER (EDUCATION)", ACADEMIC),
                ("Research Fellow", RESEARCH), ("Senior Research Fellow in Nursing", RESEARCH),
                ("Research Associate", RESEARCH), ("Postdoctoral Researcher", RESEARCH),
                ("Research Assistant", RESEARCH),
                ("Administrator", OTHER), ("Research Administrator", OTHER), ("Lecturer Support Officer", OTHER),
                ("Senior Technical Officer", OTHER), ("Technician", OTHER), ("School Manager", OTHER),
                ("Administrative Assistant", OTHER), ("Placement Co-ordinator", OTHER),
                ("Proofreader", None), ("Chaplain", None), ("", None), (None, None)):
            self.assertEqual(classify(title)[0], kind, title)

    def test_the_deciding_phrase(self):
        self.assertEqual(classify("Lecturer Support Officer"), (OTHER, "support officer"))
        self.assertEqual(classify("Senior Lecturer in Business Administration"), (ACADEMIC, "lecturer"))

    def test_a_tie_is_unknown(self):
        self.assertEqual(classify("Fellow Porter", {ACADEMIC: ['fellow'], OTHER: ['porter']}), (None, None))

    @override_settings(WAM_JOB_TITLE_PATTERNS={ACADEMIC: ['tutor'], RESEARCH: [], OTHER: ['lecturer']})
    def test_patterns_from_settings(self):
        self.assertEqual(classify("Tutor")[0], ACADEMIC)
        self.assertEqual(classify("Lecturer")[0], OTHER)


class JobTitleTestCase(SchoolGroupsTestCase):
    """The School groups set-up, with Biomed's Academic and Admin Staff subgroups"""

    def titled(self, staff, title, has_workload=True):
        staff.job_title = title
        staff.has_workload = has_workload
        staff.save()
        return staff


class ApplyTests(JobTitleTestCase):

    def test_academic(self):
        self.titled(self.lecturer, "Senior Lecturer", has_workload=False)
        self.assertEqual(apply_suggestion(self.lecturer), [f"added to {self.academic.name}", "has workload"])
        self.lecturer.refresh_from_db()
        self.assertTrue(self.lecturer.has_workload)
        self.assertIn(self.academic, self.lecturer.user.groups.all())

    def test_admin(self):
        self.titled(self.secretary, "School Administrator")
        apply_suggestion(self.secretary)
        self.secretary.refresh_from_db()
        self.assertFalse(self.secretary.has_workload)
        self.assertIn(self.admin_staff, self.secretary.user.groups.all())

    def test_research(self):
        self.titled(self.nobody, "Research Fellow")
        self.assertEqual(apply_suggestion(self.nobody), [])  # left for each person to decide
        self.assertEqual(apply_suggestion(self.nobody, new=True), ["no workload"])  # a new person starts without
        self.assertFalse(self.nobody.user.groups.filter(pk__in=[self.academic.pk, self.admin_staff.pk]).exists())

    def test_decisions_already_made_stand(self):
        self.titled(self.lecturer, "Lecturer", has_workload=False)
        self.lecturer.user.groups.add(self.admin_staff)
        self.assertEqual(apply_suggestion(self.lecturer), [])
        self.lecturer.refresh_from_db()
        self.assertFalse(self.lecturer.has_workload)

    def test_unknown_and_external(self):
        self.assertEqual(apply_suggestion(self.titled(self.nobody, "Chaplain")), [])
        self.assertEqual(apply_suggestion(self.titled(self.examiner, "Professor")), [])

    def test_no_subgroups(self):
        school = School.objects.create(name="School of Nowhere")
        self.lecturer.school = school
        self.titled(self.lecturer, "Lecturer", has_workload=False)
        self.assertEqual(apply_suggestion(self.lecturer), ["has workload"])
        self.assertIsNone(Suggestion(self.lecturer).group)


class OnboardingTests(JobTitleTestCase):

    def test_new_people_get_the_suggestion(self):
        staff, created = onboard_staff_record({'username': 'newlecturer', 'job_title': "Lecturer in Physiology",
                                               'school': self.biomed.name})
        self.assertTrue(created)
        self.assertIn(self.academic, staff.user.groups.all())
        staff, created = onboard_staff_record({'username': 'newadmin', 'job_title': "Technician",
                                               'school': self.biomed.name})
        self.assertFalse(Staff.objects.get(pk=staff.pk).has_workload)

    def test_existing_people_are_left_alone(self):
        self.titled(self.secretary, "Administrator")
        staff, created = onboard_staff_record({'username': self.secretary.user.username,
                                               'job_title': "Administrator", 'school': self.biomed.name})
        self.assertFalse(created)
        self.assertTrue(Staff.objects.get(pk=self.secretary.pk).has_workload)
        self.assertNotIn(self.admin_staff, self.secretary.user.groups.all())


class SchoolGroupsPageTests(JobTitleTestCase):

    def test_suggestions_shown(self):
        self.titled(self.lecturer, "Lecturer")
        self.titled(self.secretary, "Administrator")
        self.secretary.user.groups.add(self.admin_staff)
        self.titled(self.nobody, "Research Fellow")
        response = self.page(self.local_admin)
        rows = {row['staff']: row for row in response.context['rows']}
        self.assertEqual(rows[self.lecturer]['suggestion'].kind, ACADEMIC)
        self.assertEqual(rows[self.lecturer]['suggested_group'], self.academic)
        self.assertTrue(rows[self.lecturer]['differs'])  # not in Academic Staff yet
        self.assertTrue(rows[self.secretary]['differs'])  # has a workload, which admin staff don't
        self.assertFalse(rows[self.nobody]['differs'])  # research: nothing to differ from
        self.assertContains(response, "Lecturer")
        self.assertContains(response, 'data-suggest-group="%d"' % self.academic.pk)
        self.assertContains(response, "Apply suggestions")

    def test_saving_workloads(self):
        self.titled(self.lecturer, "Lecturer", has_workload=False)
        self.titled(self.secretary, "Administrator", has_workload=True)
        self.save_workloads(self.local_admin, [self.lecturer, self.local_admin, self.nobody])
        self.assertTrue(Staff.objects.get(pk=self.lecturer.pk).has_workload)
        self.assertFalse(Staff.objects.get(pk=self.secretary.pk).has_workload)
        self.assertEqual(LogEntry.objects.count(), 2)

    def test_workloads_outside_the_page_are_untouched(self):
        self.titled(self.computing_lecturer, "Lecturer", has_workload=True)
        self.client.force_login(self.local_admin.user)
        data = {'workload_shown': '1'}
        data.update({f'w-{s.pk}': 'on' for s in self.scope().people})
        self.client.post(reverse('school_groups'), data)
        self.assertTrue(Staff.objects.get(pk=self.computing_lecturer.pk).has_workload)
        self.assertTrue(Staff.objects.get(pk=self.examiner.pk).has_workload is not None)

    def test_forms_without_the_column_leave_workloads_alone(self):
        self.save(self.local_admin, [])
        self.assertTrue(Staff.objects.get(pk=self.lecturer.pk).has_workload)


class ReportTests(JobTitleTestCase):

    def test_report_then_apply(self):
        self.titled(self.lecturer, "Lecturer", has_workload=False)
        self.titled(self.secretary, "Administrator")
        self.titled(self.nobody, "Chaplain")
        out = io.StringIO()
        call_command('report_job_titles', '--school', self.biomed.name, stdout=out)
        report = out.getvalue()
        self.assertIn("Academic:", report)
        self.assertIn('Lecturer  ("lecturer")', report)
        self.assertIn("Chaplain", report)
        self.assertIn("Nothing changed", report)
        self.assertFalse(Staff.objects.get(pk=self.lecturer.pk).has_workload)

        out = io.StringIO()
        call_command('report_job_titles', '--school', self.biomed.name, '--apply', stdout=out)
        self.assertTrue(Staff.objects.get(pk=self.lecturer.pk).has_workload)
        self.assertIn(self.admin_staff, self.secretary.user.groups.all())
        self.assertIn("Changed 2 people", out.getvalue())
