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
                                       size=modulesize)

        module.moderators.add(moderator)
        module.programmes.add(lead_programme)
        module.programmes.add(other_programme)
        module.save()

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
            deadline="2050-01-01 00:00:00",
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
            print(f"Testing non authenticated user access: {url}")
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
                    #"/programmes/details/1" #TODO: 301 handling?
                    "/projects/index/",
                    "/cadmin/",
                    "/cadmin/assessment_staff/index/",
                    ]:
            print(f"Testing non authenticated user access: {url}", file=sys.stderr)
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


    def test_external_index_pages(self):
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
        #TODO: Need to establish if this is the best way to do this.
        response = self.client.get("/cadmin/assessment_staff/index/")
        self.assertRaisesMessage(PermissionDenied, "You do not have admin permissions.")


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
