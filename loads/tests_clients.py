# Standard Imports
import sys, logging
from io import StringIO

from django.core.exceptions import PermissionDenied
# Django specific Imports
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

# Import Some Django models that we use

from django.contrib.auth.models import User, Group


# Import some models

from .models import ActivityGenerator
from .models import ActivitySet
from .models import ActivityType
from .models import Activity
from .models import AssessmentResource
from .models import AssessmentResourceType
from .models import AssessmentStaff
from .models import Category
from .models import Campus
from .models import ExternalExaminer
from .models import Staff
from .models import Task
from .models import Activity
from .models import TaskCompletion
from .models import Module
from .models import ModuleSize
from .models import ModuleStaff
from .models import Programme
from .models import Project
from .models import ProjectStaff
from .models import WorkPackage

from WAM.settings import LOGIN_URL
from WAM.settings import WAM_ADFS_AUTH




class UserClientTest(TestCase):
    """
    Tests for access directly by web clients.

    These are relatively simple at present and mainly try to ensure views aren't broken on open.
    """

    def setUp(self):
        # Logging is very noisy typically
        logging.disable(logging.CRITICAL)

        # Every test needs a client.
        self.client = Client()

        user_staff = User.objects.create_user('user', 'a@b.com', 'password')
        user_superuser = User.objects.create_superuser('admin', 'a@b.com', 'password')
        user_external = User.objects.create_user('external', 'a@b.com', 'password')

        staff_staff = Staff.objects.get(user=user_staff)
        staff_staff.is_external = False
        staff_superuser = Staff.objects.get(user=user_superuser)
        staff_superuser.is_external = False
        staff_external = Staff.objects.get(user=user_external)
        staff_external.is_external = True

        # Create a workpackage
        package = WorkPackage.objects.create(name="test", startdate="2017-09-01", enddate="2018-08-31")
        group = Group.objects.create(name="test")
        package.groups.add(group)
        package.save()
        user_staff.groups.add(group)
        user_staff.save()

        staff_staff.package = package
        staff_staff.save()
        staff_external.package = package
        staff_external.save()
        staff_superuser.package = package
        staff_superuser.save()

        # Create a campus
        campus = Campus.objects.create(name="campus")

        # Create a Category and ActivityType
        category = Category.objects.create(name="Education", abbreviation="education", colour="red")
        ActivityType.objects.create(name="Lecturing", category=category)

        # Create a Module Size
        modulesize = ModuleSize.objects.create(text="50", admin_scaling=1.0, assessment_scaling=1.0)

        # Create some Users
        user_aA = User.objects.create(username="academicA", password="test")
        user_aB = User.objects.create(username="academicB", password="test")
        user_aC = User.objects.create(username="academicC", password="test")
        user_aD = User.objects.create(username="academicD", password="test")
        user_aE = User.objects.create(username="academicE", password="test")

        user_aF = User.objects.create(username="assessmentstaffA", password="test")

        user_eA = User.objects.create(username="externalA", password="test")
        user_eB = User.objects.create(username="externalB", password="test")
        user_eC = User.objects.create(username="externalC", password="test")

        # Create linked Staff and ExternalExaminers
        coordinator = Staff.objects.get(user=user_aA)
        team_member = Staff.objects.get(user=user_aB)
        resource_owner = Staff.objects.get(user=user_aC)
        moderator = Staff.objects.get(user=user_aD)
        other_staff = Staff.objects.get(user=user_aE)

        assessment_staff = Staff.objects.get(user=user_aF)

        lead_examiner = Staff.objects.get(user=user_eA)
        lead_examiner.is_external = True
        lead_examiner.save()
        associated_examiner = Staff.objects.get(user=user_eB)
        associated_examiner.is_external = True
        associated_examiner.save()
        other_examiner = Staff.objects.get(user=user_eC)
        other_examiner.is_external = True
        other_examiner.save()

        # Add the user to AssessmentStaff
        AssessmentStaff.objects.create(staff=assessment_staff, package=package)

        # Create some programmes
        lead_programme = Programme.objects.create(
            programme_code="123",
            programme_name="BSc Breaking Things",
            package=package)

        lead_programme.examiners.add(lead_examiner)
        lead_programme.save()

        other_programme = Programme.objects.create(
            programme_code="456",
            programme_name="MSc Breaking Things",
            package=package)

        other_programme.examiners.add(associated_examiner)
        other_programme.save()

        # Create a module with staffA as coordinator and staff
        module = Module.objects.create(module_code="ABC101",
                                       module_name="Breaking Things",
                                       package=package,
                                       coordinator=coordinator,
                                       lead_programme=lead_programme,
                                       campus=campus,
                                       size=modulesize,
                                       number_students=30)

        module.moderators.add(moderator)
        module.programmes.add(lead_programme)
        module.programmes.add(other_programme)
        module.save()

        # Module ABC101 is in programme 123 as a lead programme
        # Module ABC101 in in programme 456 as a programme (but not lead)

        # Programme 123 has an examiner "externalA" (a lead examiner)
        # Programme 456 has an examiner "externalB" (an examiner but not lead)

        # So "external" and "externalC" are externals with nothing to examine

        # and staffB on teaching team
        ModuleStaff.objects.create(
            module=module,
            staff=team_member,
            contact_proportion=50,
            admin_proportion=50,
            assessment_proportion=50,
            package=package)

        # Create an AssessmentResourceType
        resource_type = AssessmentResourceType.objects.create(name="exam")

        # Create a resource, with staffC as an owner
        resource = AssessmentResource.objects.create(
            name="test",
            module=module,
            owner=resource_owner,
            resource_type=resource_type)

        # Create a Task
        task = Task.objects.create(
            name="test",
            category=category,
            details="A simple test task",
            deadline="2050-01-01 00:00:00Z",
        )

        task.targets.add(staff_staff)

    def tearDown(self):
        # Put the logging back in place
        logging.disable(logging.NOTSET)


    def test_not_logged_in(self):
        """
        Some checks that unauthenticated users (and web crawlers) do not have access they should not have.
        """

        # Deliberately no login code here
        if WAM_ADFS_AUTH:
            login_url = "/oauth2/login"
        else:
            login_url = LOGIN_URL

        # Some views are expected to be ok.
        for url in ["/",
                    "/external/"
                    ]:
            #print(f"Testing non authenticated user access: {url}")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        for url in ["/loads/",
                    "/loads/modules/",
                    "/loads_charts/",
                    "/activities/index/",
                    "/generators/index/",
                    "/tasks/index/",
                    "/tasks/archived/index/",
                    "/modules/index/",
                    "/programmes/index/",
                    "/projects/index/",
                    "/cadmin/",
                    "/cadmin/assessment_staff/index/",
                    ]:
            #print(f"Testing non authenticated user access: {url}", file=sys.stderr)
            redirected_url = f"{login_url}?next={url}"
            response = self.client.get(url)
            try:
                self.assertRedirects(response, redirected_url, fetch_redirect_response=False, status_code=302, target_status_code=302)
            except AssertionError as e:
                print(f"failed url was {url}")
                raise


    def test_loads_no_workpackage(self):
        """A user with no Workpckage should be redirected."""

        # Log the User in
        user_staff = User.objects.get(username='user')
        self.client.force_login(user_staff)

        staff_staff = Staff.objects.get(user=user_staff)
        staff_staff.package = None
        staff_staff.save()

        # No Workpackage is set, so it should redirect
        response = self.client.get("/loads/")

        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 302)
        # Check it's trying to change the Workpackage
        self.assertEqual(response['location'], '/workpackage/change/')


    def test_superuser_index_pages(self):
        """This checks that a Superuser can access the various index pages (response code 200)"""

        # Log the User in
        admin = User.objects.get(username='admin')
        # force_login bypasses potential custom authentication back ends
        self.client.force_login(admin)

        response = self.client.get("/loads/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/loads/modules/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/loads_charts/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/activities/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/external/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/generators/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/tasks/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/tasks/archived/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/modules/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/programmes/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/projects/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/cadmin/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/cadmin/assessment_staff/index/")
        self.assertEqual(response.status_code, 200)


    def test_external_no_role_index_pages(self):
        """This checks that an External Examiner can access the various index pages, and not others"""

        # Log the User in
        external = User.objects.get(username='external')
        # force_login bypasses potential custom authentication back ends
        self.client.force_login(external)

        # These views should be response code 200 (OK)
        response = self.client.get("/external/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/programmes/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/tasks/index/")
        self.assertEqual(response.status_code, 200)

        # These views should be response code 403 (Forbidden)
        response = self.client.get("/loads/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/loads/modules/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/loads_charts/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/activities/index/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/generators/index/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/tasks/archived/index/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/modules/index/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/projects/index/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/cadmin/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/cadmin/assessment_staff/index/")
        self.assertEqual(response.status_code, 403)


    def test_staff_index_pages(self):
        """This checks that a Staff member can access the various index pages, and not others"""

        # Log the User in
        user = User.objects.get(username='user')
        staff = Staff.objects.get(user=user)
        # force_login bypasses potential custom authentication back ends
        self.client.force_login(user)

        # Check the packages, we will get redirects if this isn't right
        self.assertEqual(len(staff.get_all_packages()), 1)
        self.assertIsNotNone(staff.package)

        # These views should be response code 200 (OK)
        response = self.client.get("/programmes/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/loads/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/loads/modules/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/loads_charts/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/tasks/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/activities/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/generators/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/tasks/archived/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/modules/index/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/external/")
        self.assertEqual(response.status_code, 200)

        # These views should be response code 403 (Forbidden) for a regular member of staff with no other permissions
        response = self.client.get("/projects/index/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/cadmin/")
        self.assertEqual(response.status_code, 403)

        #TODO: This test is reporting 302 in oauth authentication. Not sure how to capture that.
        #TODO: Need to establish if this is the best way to do this. Maybe check it isn't 200 for now.
        response = self.client.get("/cadmin/assessment_staff/index/")
        self.assertNotEqual(response.status_code, 200)
        self.assertRaisesMessage(PermissionDenied, "You do not have admin permissions.")


    def test_staff_no_role_module_pages(self):
        """This checks that a Staff member with no specific has appropriate module views"""

        # Log the User in
        user = User.objects.get(username='user')
        staff = Staff.objects.get(user=user)
        # force_login bypasses potential custom authentication back ends
        self.client.force_login(user)

        module = Module.objects.get(module_code="ABC101")

        # These views should be response code 200 (OK)
        response = self.client.get("/modules/details/%u" % module.id)
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/modules/add_assessment_sign_off/%u" % module.id)
        self.assertEqual(response.status_code, 200)

        # These views should be response code 404 (Not Found)
        response = self.client.get("/modules/details/9999")
        self.assertEqual(response.status_code, 404)

        # These views should be response code 403 (Forbidden)
        response = self.client.get("/modules/create/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/modules/update/%u" % module.id)
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/modules/delete/%u" % module.id)
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/modules/add_assessment_resource/%u" % module.id)
        self.assertEqual(response.status_code, 403)


    def test_external_no_role_module_pages(self):
        """This checks that a Staff member with no specific has appropriate module views"""

        # Log the User in
        user = User.objects.get(username='externalC')
        staff = Staff.objects.get(user=user)
        # force_login bypasses potential custom authentication back ends
        self.client.force_login(user)

        module = Module.objects.get(module_code="ABC101")

        # These might be a redirect, which could be different with oauth2, but it should not be 200
        response = self.client.get("/modules/details/%u" % module.id)
        self.assertNotEqual(response.status_code, 200)

        response = self.client.get("/modules/add_assessment_sign_off/%u" % module.id)
        self.assertEqual(response.status_code, 200)

        # These views should be response code 404 (Not Found)
        response = self.client.get("/modules/details/9999")
        self.assertEqual(response.status_code, 404)

        # These views should be response code 403 (Forbidden)
        response = self.client.get("/modules/create/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/modules/update/%u" % module.id)
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/modules/delete/%u" % module.id)
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/modules/add_assessment_resource/%u" % module.id)
        self.assertEqual(response.status_code, 403)


    def test_external_with_role_module_pages(self):
        """This checks that a Staff member with no specific has appropriate module views"""

        # Log the User in
        user = User.objects.get(username='externalA')
        staff = Staff.objects.get(user=user)
        # force_login bypasses potential custom authentication back ends
        self.client.force_login(user)

        module = Module.objects.get(module_code="ABC101")

        # Should be OK
        response = self.client.get("/modules/details/%u" % module.id)
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/modules/add_assessment_resource/%u" % module.id)
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/modules/add_assessment_sign_off/%u" % module.id)
        self.assertEqual(response.status_code, 200)

        # These views should be response code 404 (Not Found)
        response = self.client.get("/modules/details/9999")
        self.assertEqual(response.status_code, 404)

        # These views should be response code 403 (Forbidden)
        response = self.client.get("/modules/create/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/modules/update/%u" % module.id)
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/modules/delete/%u" % module.id)
        self.assertEqual(response.status_code, 403)


    def test_superuser_module_pages(self):
        """This checks that a Staff member with no specific has appropriate module views"""

        # Log the User in
        user = User.objects.get(username='admin')
        staff = Staff.objects.get(user=user)
        # force_login bypasses potential custom authentication back ends
        self.client.force_login(user)

        module = Module.objects.get(module_code="ABC101")

        # These views should be response code 200 (OK)
        response = self.client.get("/modules/details/%u" % module.id)
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/modules/add_assessment_resource/%u" % module.id)
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/modules/add_assessment_sign_off/%u" % module.id)
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/modules/create/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/modules/update/%u" % module.id)
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/modules/delete/%u" % module.id)
        self.assertEqual(response.status_code, 200)

        # These views should be response code 404 (Not Found)
        response = self.client.get("/modules/details/9999")
        self.assertEqual(response.status_code, 404)


    def test_staff_no_role_programme_pages(self):
        """This checks that a Staff member with no specific has appropriate programme views"""

        # Log the User in
        user = User.objects.get(username='user')
        staff = Staff.objects.get(user=user)
        # force_login bypasses potential custom authentication back ends
        self.client.force_login(user)

        programme = Programme.objects.get(programme_code="123")

        # These views should be response code 200 (OK)
        response = self.client.get("/programmes/details/%u" % programme.id)
        self.assertEqual(response.status_code, 200)

        # These views should be response code 403 (Forbidden)
        response = self.client.get("/programmes/update/%u" % programme.id)
        self.assertEqual(response.status_code, 403)

        # These views should be response code 404 (Not Found)
        response = self.client.get("/programmes/update/9999")
        self.assertEqual(response.status_code, 403)

        # These views should be response code 403 (Forbidden)
        response = self.client.get("/programmes/create/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/programmes/delete/%u" % programme.id)
        self.assertEqual(response.status_code, 403)

        # These views should be response code 404 (Not Found)
        response = self.client.get("/programmes/details/9999")
        self.assertEqual(response.status_code, 404)


    def test_external_programme_pages(self):
        """This checks that a Staff member with no specific has appropriate module views"""

        # Log the User in
        user = User.objects.get(username='external')
        staff = Staff.objects.get(user=user)
        # force_login bypasses potential custom authentication back ends
        self.client.force_login(user)

        programme = Programme.objects.get(programme_code="123")

        # These views should be response code 200 (OK)
        response = self.client.get("/programmes/details/%u" % programme.id)
        self.assertEqual(response.status_code, 200)

        # These views should be response code 403 (Forbidden)
        response = self.client.get("/programmes/update/%u" % programme.id)
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/programmes/update/9999")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/programmes/create/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/programmes/delete/%u" % programme.id)
        self.assertEqual(response.status_code, 403)

        # These views should be response code 404 (Not Found)
        response = self.client.get("/programmes/details/9999")
        self.assertEqual(response.status_code, 404)


    def test_superuser_programme_pages(self):
        """This checks that a Staff member with no specific has appropriate module views"""

        # Log the User in
        user = User.objects.get(username='admin')
        staff = Staff.objects.get(user=user)
        # force_login bypasses potential custom authentication back ends
        self.client.force_login(user)

        programme = Programme.objects.get(programme_code="123")

        # These views should be response code 200 (OK)
        response = self.client.get("/programmes/details/%u" % programme.id)
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/programmes/update/%u" % programme.id)
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/programmes/create/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/programmes/delete/%u" % programme.id)
        self.assertEqual(response.status_code, 200)

        # These views should be response code 404 (Not Found)
        response = self.client.get("/programmes/details/9999")
        self.assertEqual(response.status_code, 404)

        response = self.client.get("/programmes/update/9999")
        self.assertEqual(response.status_code, 404)


    def test_staff_task_pages(self):
        """This checks that a Staff member can access the various task views"""

        # Log the User in
        user = User.objects.get(username='user')
        staff = Staff.objects.get(user=user)
        # force_login bypasses potential custom authentication back ends
        self.client.force_login(user)

        # Fetch the task we created
        task = Task.objects.get(name="test")

        # Check the packages, we will get redirects if this isn't right
        self.assertEqual(len(staff.get_all_packages()), 1)
        self.assertIsNotNone(staff.package)

        # These views should be response code 200 (OK)
        response = self.client.get("/tasks/index/")
        self.assertEqual(response.status_code, 200)
        #TODO: Check task count (after UX update)

        response = self.client.get("/tasks/archived/index/")
        self.assertEqual(response.status_code, 200)
        # TODO: Check task count (after UX update)

        response = self.client.get("/tasks/detail/%s" % task.id)
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/tasks/completion/%s/%s" % (task.id, staff.id))
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/tasks/bystaff/%s" % staff.id)
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/tasks/create/")
        self.assertEqual(response.status_code, 200)

        #TODO: Add completion form submission
        #TODO: Check archive works
        #TODO: Add admin views

class HourCalculationTest(TestCase):
    """Tests for formula-based hour calculations on Module."""

    def setUp(self):
        logging.disable(logging.CRITICAL)

        user = User.objects.create_user('calcuser', 'a@b.com', 'password')
        campus = Campus.objects.create(name="campus")
        category = Category.objects.create(
            name="Admin", abbreviation="admin", colour="blue")
        self.activity_type = ActivityType.objects.create(
            name="Coordination", category=category)

        self.package = WorkPackage.objects.create(
            name="test",
            startdate="2024-09-01",
            enddate="2025-08-31",
            credit_contact_scaling=2.5,
            contact_admin_scaling=1.0,
            contact_assessment_scaling=1.0,
            coordinator_formula='15 + students * 0.01',
            coordinator_activity_type=self.activity_type,
        )
        group = Group.objects.create(name="calcgroup")
        self.package.groups.add(group)

        coordinator_user = User.objects.create_user('coord', 'c@b.com', 'password')
        self.coordinator = Staff.objects.get(user=coordinator_user)
        self.coordinator.package = self.package
        self.coordinator.save()

        self.module = Module.objects.create(
            module_code="CALC101",
            module_name="Calculation Test",
            package=self.package,
            coordinator=self.coordinator,
            campus=campus,
            number_students=100,
            credits=20,
            semester="1,2",
        )

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_contact_hours_formula(self):
        """Contact hours should be credits * scaling when no override."""
        expected = 20 * 2.5  # credits * credit_contact_scaling
        self.assertAlmostEqual(self.module.get_contact_hours(), expected)

    def test_contact_hours_override(self):
        """Manual contact hours override should take precedence over formula."""
        self.module.contact_hours = 99
        self.module.save()
        self.assertEqual(self.module.get_contact_hours(), 99.0)

    def test_admin_hours_uses_contact(self):
        """Admin hours should be based on get_contact_hours(), respecting overrides."""
        self.module.contact_hours = 40
        self.module.save()
        expected = 40 * 1.0  # contact * contact_admin_scaling
        self.assertAlmostEqual(self.module.get_admin_hours(), expected)

    def test_coordinator_hours_formula(self):
        """Coordinator hours should follow the package formula."""
        expected = 15 + 100 * 0.01  # 15 + students * 0.01
        self.assertAlmostEqual(self.module.get_coordinator_hours(), expected)

    def test_coordinator_hours_override(self):
        """Manual coordinator hours override should take precedence."""
        self.module.coordinator_hours = 25
        self.module.save()
        self.assertAlmostEqual(self.module.get_coordinator_hours(), 25.0)

    def test_coordinator_hours_no_coordinator(self):
        """Module with no coordinator should return 0 coordinator hours."""
        self.module.coordinator = None
        self.module.save()
        self.assertEqual(self.module.get_coordinator_hours(), 0)

    def test_coordinator_hours_no_formula(self):
        """Package with no coordinator formula should return 0."""
        self.package.coordinator_formula = ''
        self.package.save()
        self.assertEqual(self.module.get_coordinator_hours(), 0.0)

    def test_get_all_hours_includes_coordinator(self):
        """get_all_hours() should include coordinator hours."""
        contact = self.module.get_contact_hours()
        admin = self.module.get_admin_hours()
        assessment = self.module.get_assessment_hours()
        coordinator = self.module.get_coordinator_hours()
        self.assertAlmostEqual(
            self.module.get_all_hours(),
            contact + admin + assessment + coordinator
        )

    def test_semester_split_two_semesters(self):
        """Hours should be split equally across two semesters."""
        hours = self.module.get_contact_hours_by_semester()
        self.assertAlmostEqual(hours[0], hours[1] + hours[2] + hours[3])
        self.assertAlmostEqual(hours[1], hours[2])
        self.assertEqual(hours[3], 0)

    def test_semester_split_single_semester(self):
        """Hours should fall entirely in one semester."""
        self.module.semester = "2"
        self.module.save()
        hours = self.module.get_contact_hours_by_semester()
        self.assertEqual(hours[1], 0)
        self.assertGreater(hours[2], 0)
        self.assertEqual(hours[3], 0)


class StaffHourTotalsTest(TestCase):
    """Tests that Staff hour aggregation methods include all sources correctly."""

    def setUp(self):
        logging.disable(logging.CRITICAL)

        campus = Campus.objects.create(name="campus")
        category = Category.objects.create(
            name="Admin", abbreviation="adm", colour="blue")
        activity_type = ActivityType.objects.create(
            name="Coordination", category=category)

        self.package = WorkPackage.objects.create(
            name="test",
            startdate="2024-09-01",
            enddate="2025-08-31",
            credit_contact_scaling=2.5,
            contact_admin_scaling=1.0,
            contact_assessment_scaling=1.0,
            coordinator_formula='15 + students * 0.01',
            coordinator_activity_type=activity_type,
        )
        group = Group.objects.create(name="totalsgroup")
        self.package.groups.add(group)

        coord_user = User.objects.create_user('coordtotal', 'x@b.com', 'password')
        self.coordinator = Staff.objects.get(user=coord_user)
        self.coordinator.package = self.package
        self.coordinator.save()

        self.module = Module.objects.create(
            module_code="TOT101",
            module_name="Totals Test",
            package=self.package,
            coordinator=self.coordinator,
            campus=campus,
            number_students=100,
            credits=20,
            semester="1",
        )

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_hours_by_semester_includes_coordinator(self):
        """hours_by_semester() total should include coordinator hours."""
        coord_hours = self.module.get_coordinator_hours()
        semester_info = self.coordinator.hours_by_semester(package=self.package)
        self.assertGreaterEqual(semester_info[0], coord_hours)

    def test_hours_by_category_includes_coordinator(self):
        """hours_by_category() should include coordinator hours in the right category."""
        coord_hours = self.module.get_coordinator_hours()
        by_category = self.coordinator.hours_by_category(package=self.package)
        total = sum(by_category.values())
        self.assertGreaterEqual(total, coord_hours)

    def test_semester_totals_consistent(self):
        """Total hours should equal sum of semester hours."""
        semester_info = self.coordinator.hours_by_semester(package=self.package)
        self.assertAlmostEqual(
            semester_info[0],
            semester_info[1] + semester_info[2] + semester_info[3]
        )


class ActivitiesViewTest(TestCase):
    """Tests for the activities view totals and coordinator hour display."""

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.client = Client()

        campus = Campus.objects.create(name="campus")
        category = Category.objects.create(
            name="Admin", abbreviation="adm", colour="blue")
        activity_type = ActivityType.objects.create(
            name="Coordination", category=category)

        self.package = WorkPackage.objects.create(
            name="test",
            startdate="2024-09-01",
            enddate="2025-08-31",
            credit_contact_scaling=2.5,
            contact_admin_scaling=1.0,
            contact_assessment_scaling=1.0,
            coordinator_formula='15 + students * 0.01',
            coordinator_activity_type=activity_type,
        )
        group = Group.objects.create(name="actgroup")
        self.package.groups.add(group)

        user = User.objects.create_user('actuser', 'a@b.com', 'password')
        user.groups.add(group)
        self.staff = Staff.objects.get(user=user)
        self.staff.package = self.package
        self.staff.save()

        self.module = Module.objects.create(
            module_code="ACT101",
            module_name="Activities Test",
            package=self.package,
            coordinator=self.staff,
            campus=campus,
            number_students=100,
            credits=20,
            semester="1,2",
        )

        ModuleStaff.objects.create(
            module=self.module,
            staff=self.staff,
            contact_proportion=100,
            admin_proportion=100,
            assessment_proportion=100,
            package=self.package,
            activity_type=activity_type,
        )

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_activities_view_loads(self):
        self.client.force_login(self.staff.user)
        response = self.client.get(f"/activities/{self.staff.id}")
        self.assertEqual(response.status_code, 200)

    def test_activities_view_includes_coordinator_row(self):
        self.client.force_login(self.staff.user)
        response = self.client.get(f"/activities/{self.staff.id}")
        self.assertContains(response, "Coordination")

    def test_activities_view_totals_consistent(self):
        self.client.force_login(self.staff.user)
        response = self.client.get(f"/activities/{self.staff.id}")
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertAlmostEqual(
            ctx['total'],
            ctx['semester1_total'] + ctx['semester2_total'] + ctx['semester3_total'],
            places=2,
        )