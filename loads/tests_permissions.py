"""Tests for permissions: who may set assessment states, and the access decorators"""
import logging
import unittest

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from .decorators import admin_only, external_only, staff_only
from .models import AssessmentStaff, AssessmentState, Staff
from .testing import (add_assessment_staff, allocate, make_module, make_package, make_programme,
                      make_staff, make_state)


class AssessmentStateTestCase(TestCase):
    """AssessmentState.can_be_set_by() for each kind of actor"""

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.package = make_package()
        self.coordinator = make_staff('coordinator', package=self.package)
        self.moderator = make_staff('moderator', package=self.package)
        self.team_member = make_staff('team', package=self.package)
        self.assessment_staff = make_staff('assessment', package=self.package)
        self.other = make_staff('other', package=self.package)
        self.superuser = make_staff('admin', package=self.package, superuser=True)
        self.examiner = make_staff('examiner', package=self.package, is_external=True)
        self.other_examiner = make_staff('otherexaminer', package=self.package, is_external=True)

        self.module = make_module(self.package, coordinator=self.coordinator)
        self.module.moderators.add(self.moderator)
        allocate(self.team_member, self.module)
        add_assessment_staff(self.assessment_staff, self.package)
        self.module.lead_programme = make_programme(self.package, examiners=[self.examiner])
        self.module.save()

        self.internal = [self.coordinator, self.moderator, self.team_member, self.assessment_staff, self.other]

    def allowed(self, actors):
        """The staff among all of the above who may set a state with these actors"""
        state = make_state(actors=actors)
        everyone = self.internal + [self.superuser, self.examiner, self.other_examiner]
        return {staff.user.username for staff in everyone if state.can_be_set_by(staff, self.module)}

    def test_coordinator(self):
        self.assertEqual(self.allowed('coordinator'), {'coordinator', 'admin'})

    def test_moderator(self):
        self.assertEqual(self.allowed('moderator'), {'moderator', 'admin'})

    def test_team_member(self):
        self.assertEqual(self.allowed('team_member'), {'team', 'admin'})

    def test_assessment_staff(self):
        self.assertEqual(self.allowed('assessment_staff'), {'assessment', 'admin'})

    def test_assessment_staff_in_another_package(self):
        AssessmentStaff.objects.filter(staff=self.assessment_staff).delete()
        add_assessment_staff(self.assessment_staff, make_package("Other"))
        self.assertEqual(self.allowed('assessment_staff'), {'admin'})

    def test_anyone_means_any_internal_staff(self):
        self.assertEqual(self.allowed('anyone'),
                         {'coordinator', 'moderator', 'team', 'assessment', 'other', 'admin'})

    def test_external(self):
        """Only examiners of the module's programmes, never internal staff (bar superusers)"""
        self.assertEqual(self.allowed('external'), {'examiner', 'admin'})

    def test_external_via_other_programme(self):
        self.module.programmes.add(make_programme(self.package, code="P2", examiners=[self.other_examiner]))
        self.assertEqual(self.allowed('external'), {'examiner', 'otherexaminer', 'admin'})

    def test_examiners_cannot_set_internal_states(self):
        self.assertEqual(self.allowed('coordinator,moderator,team_member,anyone') &
                         {'examiner', 'otherexaminer'}, set())

    def test_several_actors(self):
        self.assertEqual(self.allowed('coordinator,moderator'), {'coordinator', 'moderator', 'admin'})

    @unittest.expectedFailure
    def test_actors_with_spaces(self):
        """BUG: actors are typed in by admins, but "coordinator, moderator" silently drops the moderator"""
        self.assertEqual(self.allowed('coordinator, moderator'), {'coordinator', 'moderator', 'admin'})

    def test_external_check_needs_staff_object(self):
        state = make_state(actors='external')
        self.assertFalse(state.can_be_set_by_external(self.examiner.user, self.module))
        self.assertFalse(state.can_be_set_by_external(self.coordinator, self.module))


def view(request):
    return HttpResponse("ok")


class DecoratorTestCase(TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.factory = RequestFactory()
        self.staff = make_staff('staff')
        self.admin = make_staff('admin', is_staff=True)
        self.superuser = make_staff('super', superuser=True)
        self.external = make_staff('external', is_external=True)

    def call(self, decorator, user):
        request = self.factory.get('/')
        request.user = user
        return decorator(view)(request)

    def assertAllowed(self, decorator, user):
        self.assertEqual(self.call(decorator, user).status_code, 200)

    def assertDenied(self, decorator, user):
        with self.assertRaises(PermissionDenied):
            self.call(decorator, user)

    def test_staff_only(self):
        self.assertAllowed(staff_only, self.staff.user)
        self.assertDenied(staff_only, self.external.user)

    def test_staff_only_without_staff_object(self):
        user = User.objects.create_user('nostaff')
        Staff.objects.filter(user=user).delete()
        self.assertDenied(staff_only, user)

    def test_staff_only_creates_staff_for_superuser(self):
        Staff.objects.filter(user=self.superuser.user).delete()
        self.assertAllowed(staff_only, self.superuser.user)
        self.assertTrue(Staff.objects.filter(user=self.superuser.user).exists())

    def test_external_only(self):
        self.assertAllowed(external_only, self.external.user)
        self.assertDenied(external_only, self.staff.user)
        self.assertDenied(external_only, self.superuser.user)

    def test_external_only_without_staff_object(self):
        Staff.objects.filter(user=self.external.user).delete()
        self.assertDenied(external_only, self.external.user)

    def test_admin_only(self):
        self.assertAllowed(admin_only, self.admin.user)
        self.assertAllowed(admin_only, self.superuser.user)
        self.assertDenied(admin_only, self.staff.user)
        self.assertDenied(admin_only, AnonymousUser())

    def test_names_are_kept(self):
        self.assertEqual(staff_only(view).__name__, 'view')
