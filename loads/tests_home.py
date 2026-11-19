"""Tests for the home page: signed out, staff summary, and External Examiners"""
import datetime
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from .models import Activity, AssessmentStateSignOff, Category, Task, TaskCompletion
from .testing import allocate, make_activity_type, make_module, make_state
from .tests_views import ViewTestCase
from .views import greeting


class HomePageTestCase(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name="Admin", abbreviation="admin", colour="blue")

    def home(self, staff=None):
        if staff:
            self.login(staff)
        return self.client.get(reverse('index'))

    def task(self, name, days, staff):
        task = Task.objects.create(name=name, details="", category=self.category,
                                   deadline=timezone.now() + datetime.timedelta(days=days))
        task.targets.add(staff)
        return task


class SignedOutHomeTests(HomePageTestCase):

    def test_invites_sign_in_and_hides_the_menu(self):
        response = self.home()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('summary', response.context)
        self.assertContains(response, reverse('login'))
        self.assertContains(response, reverse('external_index'))
        for name in ('loads', 'activities_index', 'custom_admin_index'):
            self.assertNotContains(response, f'href="{reverse(name)}"', msg_prefix=name)
        self.assertNotContains(response, "Advanced administration")


class StaffHomeTests(HomePageTestCase):

    def test_workload(self):
        Activity.objects.create(name="Research", hours=30, percentage=0, package=self.package, semester='1,2',
                                activity_type=make_activity_type(), staff=self.lecturer)
        response = self.home(self.lecturer)
        summary = response.context['summary']
        self.assertEqual(summary['package'], self.package)
        self.assertEqual(summary['hours']['total'], 30)
        self.assertEqual(summary['hours']['semester1'] + summary['hours']['semester2'], 30)
        self.assertContains(response, reverse('activities', args=[self.lecturer.pk]))
        # By category, in the category's colour as in the load charts; empty categories are left out
        Category.objects.create(name="Unused", abbreviation="unused", colour="green")
        response = self.home(self.lecturer)
        self.assertEqual([(item['category'].name, item['hours']) for item in response.context['summary']['categories']],
                         [("Education", 30)])
        self.assertContains(response, "background-color: red")

    def test_no_workload_for_a_package_they_cannot_see(self):
        self.lecturer.package = self.other_package
        self.lecturer.save()
        summary = self.home(self.lecturer).context['summary']
        self.assertIsNone(summary['package'])
        self.assertNotIn('hours', summary)
        self.assertNotIn('modules', summary)

    def test_open_tasks_soonest_first(self):
        done = self.task("Done already", 1, self.lecturer)
        TaskCompletion.objects.create(task=done, staff=self.lecturer, comment="")
        later = self.task("Later", 20, self.lecturer)
        overdue = self.task("Overdue", -2, self.lecturer)
        self.task("Someone else's", 3, self.coordinator)
        summary = self.home(self.lecturer).context['summary']
        self.assertEqual([item['task'] for item in summary['tasks']], [overdue, later])
        self.assertEqual((summary['task_count'], summary['overdue_count']), (2, 1))
        self.assertTrue(summary['tasks'][0]['overdue'])

    def test_only_five_tasks_shown(self):
        for day in range(7):
            self.task(f"Task {day}", day + 1, self.lecturer)
        response = self.home(self.lecturer)
        self.assertEqual(len(response.context['summary']['tasks']), 5)
        self.assertContains(response, "and 2 more")

    def test_modules_and_roles(self):
        taught = make_module(self.package, code="COM200")
        allocate(self.coordinator, self.module)
        allocate(self.coordinator, taught)
        make_module(self.other_package, code="ELSE", coordinator=self.coordinator)
        modules = self.home(self.coordinator).context['summary']['modules']
        self.assertEqual([(item['module'], item['roles']) for item in modules],
                         [(self.module, ['Coordinator', 'Teaching']), (taught, ['Teaching'])])

    def test_sign_off_waiting(self):
        ready = make_state("Ready", actors="coordinator")
        moderated = make_state("Moderated", actors="moderator", initial_state=False)
        ready.next_states.add(moderated)
        self.module.moderators.add(self.lecturer)

        item = self.home(self.coordinator).context['summary']['modules'][0]
        self.assertTrue(item['awaiting_you'])
        self.assertIsNone(item['state'])
        item = self.home(self.lecturer).context['summary']['modules'][0]
        self.assertFalse(item['awaiting_you'])

        AssessmentStateSignOff.objects.create(module=self.module, assessment_state=ready,
                                              signed_by=self.coordinator.user, notes="")
        item = self.home(self.lecturer).context['summary']['modules'][0]
        self.assertEqual((item['state'], item['awaiting_you'], item['roles']), (ready, True, ['Moderator']))
        self.assertFalse(self.home(self.coordinator).context['summary']['modules'][0]['awaiting_you'])

    def test_waiting_sign_offs_are_counted_named_and_first(self):
        make_state("Ready", actors="coordinator")
        first = make_module(self.package, code="AAA100")  # sorts first by code, but isn't waiting
        allocate(self.coordinator, first)
        response = self.home(self.coordinator)
        summary = response.context['summary']
        self.assertEqual([item['module'] for item in summary['modules']], [self.module, first])
        self.assertEqual(summary['awaiting_count'], 1)
        self.assertEqual([state.name for state in summary['modules'][0]['next_states']], ["Ready"])
        self.assertContains(response, "1 assessment sign-off<")
        self.assertContains(response, "Sign off as Ready")

    def test_nothing_waiting(self):
        response = self.home(self.lecturer)
        self.assertEqual(response.context['summary'].get('awaiting_count'), 0)
        self.assertNotContains(response, "Waiting for you:")

    def test_superusers_are_flagged_only_for_their_own_role(self):
        make_state("Ready", actors="coordinator")
        self.module.moderators.add(self.superuser)
        item = self.home(self.superuser).context['summary']['modules'][0]
        self.assertFalse(item['awaiting_you'])
        self.assertTrue(self.module.get_next_assessment_states(self.superuser).exists())  # they still may, though

    def test_states_anyone_can_set_are_not_flagged(self):
        make_state("Comment", actors="anyone")
        self.assertFalse(self.home(self.coordinator).context['summary']['modules'][0]['awaiting_you'])

    def test_admin_link(self):
        """In the quick links only for those who can use it (the menu is unchanged)"""
        self.assertFalse(self.home(self.lecturer).context['can_use_admin'])
        self.assertTrue(self.home(self.superuser).context['can_use_admin'])

    def test_greeting(self):
        for hour, expected in ((8, "Good morning"), (13, "Good afternoon"), (19, "Good evening")):
            with mock.patch('loads.views.timezone.localtime',
                            return_value=datetime.datetime(2026, 1, 1, hour, tzinfo=datetime.timezone.utc)):
                self.assertEqual(greeting(), expected)


class ExternalHomeTests(HomePageTestCase):

    def test_examiners_are_sent_to_their_pages(self):
        response = self.home(self.examiner)
        self.assertNotIn('summary', response.context)
        self.assertContains(response, reverse('external_index'))


class NextAssessmentStatesTests(HomePageTestCase):

    def test_initial_then_following_states(self):
        ready = make_state("Ready", actors="coordinator")
        approved = make_state("Approved", actors="coordinator", initial_state=False)
        make_state("Unrelated", actors="coordinator", initial_state=False)
        ready.next_states.add(approved)
        self.assertEqual(list(self.module.get_next_assessment_states(self.coordinator)), [ready])
        self.assertEqual(list(self.module.get_next_assessment_states(self.lecturer)), [])
        AssessmentStateSignOff.objects.create(module=self.module, assessment_state=ready,
                                              signed_by=self.coordinator.user, notes="")
        self.assertEqual(self.module.get_latest_signoff().assessment_state, ready)
        self.assertEqual(list(self.module.get_next_assessment_states(self.coordinator)), [approved])


class LoginRedirectTests(HomePageTestCase):

    def test_signing_in_returns_to_the_home_page(self):
        self.lecturer.user.set_password('secret-password')
        self.lecturer.user.save()
        response = self.client.post(reverse('login'), {'username': 'lecturer', 'password': 'secret-password'})
        self.assertRedirects(response, reverse('index'), fetch_redirect_response=False)
