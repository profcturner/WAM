# Standard Imports
from io import StringIO
import logging

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


class WorkPackageMigrationTestCase(TestCase):
    def setUp(self):
        # Logging is very noisy typically
        logging.disable(logging.CRITICAL)

        # Create a workpackage
        package = WorkPackage.objects.create(name="source", startdate="2017-09-01", enddate="2018-08-31")
        destination_package = WorkPackage.objects.create(name="destination", startdate="2018-09-01",
                                                         enddate="2019-08-31")

        # Create a campus
        campus = Campus.objects.create(name="campus")

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

        # Create a module related activity

        category = Category.objects.create(name="Learning and Teaching")
        activity_type = ActivityType.objects.create(name="Exciting Activity", category=category)

        module_activity = Activity.objects.create(name="Module Activity",
                                                  activity_type=activity_type,
                                                  module=module,
                                                  hours=50,
                                                  percentage=0,
                                                  semester="1",
                                                  package=package,
                                                  staff=team_member)

        # Create a custom activity

        custom_activity = Activity.objects.create(name="Grand Wizard",
                                                  activity_type=activity_type,
                                                  hours=20,
                                                  percentage=0,
                                                  semester="1,2,3",
                                                  package=package,
                                                  staff=moderator)

        # Create a generator (with no module) and run it

        generator_no_module = ActivityGenerator.objects.create(name="Generator No Module",
                                                               hours=10,
                                                               percentage=0,
                                                               semester="1",
                                                               activity_type=activity_type,
                                                               package=package,
                                                               details="Test")

        generator_no_module.targets.add(moderator)
        generator_no_module.save()
        generator_no_module.generate_activities()

        # Create a generator (with a module) and run it

        generator_module = ActivityGenerator.objects.create(name="Generator Module",
                                                            hours=10,
                                                            percentage=0,
                                                            semester="2",
                                                            module=module,
                                                            activity_type=activity_type,
                                                            package=package,
                                                            details="Test")

        generator_module.targets.add(coordinator)
        generator_module.save()
        generator_module.generate_activities()


    def tearDown(self):
        # Put the logging back in place
        logging.disable(logging.NOTSET)


    def test_package_migration_programmes(self):
        destination = WorkPackage.objects.get(name="destination")
        source = WorkPackage.objects.get(name="source")

        # Just copy programmes first
        options = dict()
        options['copy_programmes'] = True
        options['copy_activities_generated'] = False
        options['copy_activities_custom'] = False
        options['copy_modules'] = False

        # Perform the clone
        destination.clone_from(source, options)
        # Attempt to run a second time to ensure idempotency
        destination.clone_from(source, options)

        # Get the programmes and check the numbers of each are correct
        source_programmes = Programme.objects.all().filter(package=source)
        self.assertEqual(len(source_programmes), 2)
        destination_programmes = Programme.objects.all().filter(package=destination)
        self.assertEqual(len(destination_programmes), 2)

        # Now get the individual programmes.
        source_programme_123 = source_programmes.get(programme_code="123")
        source_programme_456 = source_programmes.get(programme_code="123")
        destination_programme_123 = destination_programmes.get(programme_code="123")
        destination_programme_456 = destination_programmes.get(programme_code="123")

        # Should be trivially true
        self.assertNotEqual(source_programme_123.pk, destination_programme_123.pk)

    def test_package_migration_programmes_modules(self):
        destination = WorkPackage.objects.get(name="destination")
        source = WorkPackage.objects.get(name="source")

        # Just copy programmes first
        options = dict()
        options['copy_programmes'] = True
        options['copy_activities_generated'] = True
        options['copy_activities_custom'] = True
        options['copy_modules'] = True
        options['copy_activities_modules'] = True
        options['copy_modulestaff'] = True

        # Perform the clone
        destination.clone_from(source, options)
        # Attempt to run a second time to ensure idempotency
        destination.clone_from(source, options)

        # Get the programmes and check the numbers of each are correct
        source_programmes = Programme.objects.all().filter(package=source)
        self.assertEqual(len(source_programmes), 2)
        destination_programmes = Programme.objects.all().filter(package=destination)
        self.assertEqual(len(destination_programmes), 2)

        # And now the module counts (checks they are mapped correctly against packages)
        source_modules = Module.objects.all().filter(package=source)
        self.assertEqual(len(source_modules), 1)
        destination_modules = Module.objects.all().filter(package=destination)
        self.assertEqual(len(destination_modules), 1)

        # Now get the individual programmes.
        source_programme_123 = source_programmes.get(programme_code="123")
        source_programme_456 = source_programmes.get(programme_code="123")
        destination_programme_123 = destination_programmes.get(programme_code="123")
        destination_programme_456 = destination_programmes.get(programme_code="123")

        # Check the programme remappings
        self.assertEqual(destination_modules[0].lead_programme, destination_programme_123)
        for module_programme in destination_modules[0].programmes.all():
            self.assertTrue(module_programme in destination_programmes)

        # and modules
        source_module_ABC101 = source_modules.get(module_code="ABC101")
        destination_module_ABC101 = destination_modules.get(module_code="ABC101")

        # Moderators - check it copied
        self.assertEqual(len(destination_module_ABC101.moderators.all()), 1)

        # And now staff allocations
        source_modulestaff = ModuleStaff.objects.all().filter(package=source)
        self.assertEqual(len(source_modulestaff), 1)
        destination_modulestaff = ModuleStaff.objects.all().filter(package=destination)
        self.assertEqual(len(destination_modulestaff), 1)
        # Check the module is properly remapped
        self.assertEqual(destination_modulestaff[0].module, destination_module_ABC101)

        # And now module activities (that are not generated)
        source_module_activities = Activity.objects.all().filter(package=source).filter(module__isnull=False). \
            filter(activity_set__isnull=True)
        self.assertEqual(len(source_module_activities), 1)
        destination_module_activities = Activity.objects.all().filter(package=destination). \
            filter(activity_set__isnull=True).filter(module__isnull=False)
        self.assertEqual(len(destination_module_activities), 1)
        # Check the module is properly remapped
        self.assertEqual(destination_module_activities[0].module, destination_module_ABC101)

        # And now custom activities (not related to a module)
        source_custom_activities = Activity.objects.all().filter(package=source).filter(module__isnull=True). \
            filter(activity_set__isnull=True)
        self.assertEqual(len(source_custom_activities), 1)
        destination_custom_activities = Activity.objects.all().filter(package=destination). \
            filter(module__isnull=True).filter(activity_set__isnull=True)
        self.assertEqual(len(destination_custom_activities), 1)

        # Generated activities (no module)
        source_generated_activities = Activity.objects.all().filter(package=source).filter(module__isnull=True). \
            filter(activity_set__isnull=False)
        self.assertEqual(len(source_generated_activities), 1)
        destination_generated_activities = Activity.objects.all().filter(package=destination). \
            filter(module__isnull=True).filter(activity_set__isnull=False)
        self.assertEqual(len(destination_generated_activities), 1)

        # Generated activities (no module)
        source_generated_module_activities = Activity.objects.all().filter(package=source). \
            filter(module__isnull=False).filter(activity_set__isnull=False)
        self.assertEqual(len(source_generated_module_activities), 1)
        destination_generated_module_activities = Activity.objects.all().filter(package=destination). \
            filter(module__isnull=False).filter(activity_set__isnull=False)
        self.assertEqual(len(destination_generated_module_activities), 1)
        # Check the module is properly remapped
        self.assertEqual(destination_generated_module_activities[0].module, destination_module_ABC101)

        # Check counts on activity sets in each package to ensure they aren't cross linked
        # Originally there were two and the new activities should be cross mapped
        activity_sets = ActivitySet.objects.all()
        self.assertEqual(len(activity_sets), 4)

        # Each activity set should have precisely one activity. Let's check non modules ones first
        no_module_activity_sets = activity_sets.filter(generator__module__isnull=True)
        for activity_set in no_module_activity_sets:
            self.assertEqual(len(Activity.objects.all().filter(activity_set=activity_set)), 1)

        # And now module based ones
        module_activity_sets = activity_sets.filter(generator__module__isnull=False)

        # And there should be exactly one set per slot
        for activity_set in module_activity_sets:
            self.assertEqual(len(Activity.objects.all().filter(activity_set=activity_set)), 1)


    def test_package_migration_orphaned_modules(self):
        """A test for the correct migration of modules that have no parent programme"""
        destination = WorkPackage.objects.get(name="destination")
        source = WorkPackage.objects.get(name="source")

        # Just copy programmes first
        options = dict()
        options['copy_programmes'] = True
        options['copy_activities_generated'] = True
        options['copy_activities_custom'] = True
        options['copy_modules'] = True
        options['copy_activities_modules'] = True
        options['copy_modulestaff'] = True

        # Orphan a module
        module = Module.objects.get(module_code="ABC101")
        # Remove the lead programme
        module.lead_programme = None
        for programme in module.programmes.all():
            module.programmes.remove(programme)

        # Now perform the clone
        destination.clone_from(source, options)
        # Attempt to run a second time to ensure idempotency
        destination.clone_from(source, options)

        # check the numbers of module in each package are correct
        source_modules = Module.objects.all().filter(package=source).filter(module_code="ABC101")
        self.assertEqual(len(source_modules), 1)
        destination_modules = Module.objects.all().filter(package=destination).filter(module_code="ABC101")
        self.assertEqual(len(destination_modules), 1)

        # and modules
        #source_module_ABC101 = source_modules.get(module_code="ABC101")
        #destination_module_ABC101 = destination_modules.get(module_code="ABC101")

    def test_package_migration_module_from_otherpackage(self):
        """A test for when a module has a programme from outside the sourcepackage"""

        destination = WorkPackage.objects.get(name="destination")
        source = WorkPackage.objects.get(name="source")

        # Create an alternative source package
        alternate_source = WorkPackage.objects.create(name="alt_source", startdate="2017-09-01", enddate="2018-08-31")
        # And a programme within it
        lead_programme = Programme.objects.create(
            programme_code="987",
            programme_name="BSc Alternative Breaking Things",
            package=alternate_source)


        # Copy most stuff
        options = dict()
        options['copy_programmes'] = True
        options['copy_activities_generated'] = True
        options['copy_activities_custom'] = True
        options['copy_modules'] = True
        options['copy_activities_modules'] = True
        options['copy_modulestaff'] = True

        # Change the programme of a module to one in another workpackage
        module = Module.objects.get(module_code="ABC101")
        # Change the lead programme, remove any others
        module.lead_programme = lead_programme
        for programme in module.programmes.all():
            module.programmes.remove(programme)
        module.programmes.add(lead_programme)

        # Now perform the clone
        destination.clone_from(source, options)
        # Attempt to run a second time to ensure idempotency
        destination.clone_from(source, options)

        # check the numbers of module in each package are correct
        source_modules = Module.objects.all().filter(package=source).filter(module_code="ABC101")
        self.assertEqual(len(source_modules), 1)
        destination_modules = Module.objects.all().filter(package=destination).filter(module_code="ABC101")
        self.assertEqual(len(destination_modules), 1)


class AssessmentResourceTestCase(TestCase):
    def setUp(self):
        # Logging is very noisy typically
        logging.disable(logging.CRITICAL)

        # Create a workpackage
        package = WorkPackage.objects.create(name="test", startdate="2017-09-01", enddate="2018-08-31")

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
        lead_examiner.is_external=True
        lead_examiner.save()
        associated_examiner = Staff.objects.get(user=user_eB)
        associated_examiner.is_external=True
        associated_examiner.save()
        other_examiner = Staff.objects.get(user=user_eC)
        other_examiner.is_external=True
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

    def tearDown(self):
        # Put the logging back in place
        logging.disable(logging.NOTSET)

    def test_resource_coordinator_permissions(self):
        user = User.objects.get(username="academicA")
        coordinator = Staff.objects.get(user__username="academicA")
        resource = AssessmentResource.objects.get(name="test")

        # Coordinators should be able to download
        self.assertEqual(resource.is_downloadable_by(coordinator), True)
        self.assertEqual(resource.is_downloadable_by_staff(coordinator), True)
        self.assertEqual(resource.is_downloadable_by_external(coordinator), False)


    def test_resource_team_permissions(self):
        team_member = Staff.objects.get(user__username="academicB")
        resource = AssessmentResource.objects.get(name="test")

        # Team members should be able to download
        self.assertEqual(resource.is_downloadable_by(team_member), True)
        self.assertEqual(resource.is_downloadable_by_staff(team_member), True)
        self.assertEqual(resource.is_downloadable_by_external(team_member), False)

    def test_resource_moderator_permissions(self):
        moderator = Staff.objects.get(user__username="academicD")
        resource = AssessmentResource.objects.get(name="test")

        # Moderators should be able to download
        self.assertEqual(resource.is_downloadable_by(moderator), True)
        self.assertEqual(resource.is_downloadable_by_staff(moderator), True)
        self.assertEqual(resource.is_downloadable_by_external(moderator), False)

    def test_resource_owner_permissions(self):
        owner = Staff.objects.get(user__username="academicC")
        resource = AssessmentResource.objects.get(name="test")

        # Owners should be able to download
        self.assertEqual(resource.is_downloadable_by(owner), True)
        self.assertEqual(resource.is_downloadable_by_staff(owner), True)
        self.assertEqual(resource.is_downloadable_by_external(owner), False)

    def test_resource_assessment_staff_permissions(self):
        assessment_staff = Staff.objects.get(user__username="assessmentstaffA")
        resource = AssessmentResource.objects.get(name="test")

        # Assessment staff should be able to download
        self.assertEqual(resource.is_downloadable_by(assessment_staff), True)
        self.assertEqual(resource.is_downloadable_by_staff(assessment_staff), True)
        self.assertEqual(resource.is_downloadable_by_external(assessment_staff), False)

    def test_resource_other_staff_permissions(self):
        other = Staff.objects.get(user__username="academicE")
        resource = AssessmentResource.objects.get(name="test")

        # Others should NOT be able to download
        self.assertEqual(resource.is_downloadable_by(other), False)
        self.assertEqual(resource.is_downloadable_by_staff(other), False)
        self.assertEqual(resource.is_downloadable_by_external(other), False)

    def test_resource_lead_examiner_permissions(self):
        lead_examiner = Staff.objects.get(user__username="externalA")
        resource = AssessmentResource.objects.get(name="test")

        # Lead Examiners should be able to download
        self.assertEqual(resource.is_downloadable_by(lead_examiner), True)
        self.assertEqual(resource.is_downloadable_by_staff(lead_examiner), False)
        self.assertEqual(resource.is_downloadable_by_external(lead_examiner), True)

    def test_resource_associate_examiner_permissions(self):
        associate_examiner = Staff.objects.get(user__username="externalB")
        resource = AssessmentResource.objects.get(name="test")

        # Lead Examiners should be able to download
        self.assertEqual(resource.is_downloadable_by(associate_examiner), True)
        self.assertEqual(resource.is_downloadable_by_staff(associate_examiner), False)
        self.assertEqual(resource.is_downloadable_by_external(associate_examiner), True)

    def test_resource_other_examiner_permissions(self):
        other_examiner = Staff.objects.get(user__username="externalC")
        resource = AssessmentResource.objects.get(name="test")

        # Other Examiners should not be able to download
        self.assertEqual(resource.is_downloadable_by(other_examiner), False)
        self.assertEqual(resource.is_downloadable_by_staff(other_examiner), False)
        self.assertEqual(resource.is_downloadable_by_external(other_examiner), False)


class UserCreationTestCase(TestCase):
    """Tests for user creation functionality"""

    def setUp(self):
        # Logging is very noisy typically
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        # Put the logging back in place
        logging.disable(logging.NOTSET)

    def test_superuser_creates_staff(self):
        # Create a superuser
        user = User.objects.create_superuser(username="superuser", password="")
        # Try to get the matching staff object
        try:
            staff = Staff.objects.get(user=user)
        except:
            staff = None

        # Check the matching staff object has been created
        self.assertIsNotNone(staff)

        # That staff member should not be External
        self.assertFalse(staff.is_external)

        # That staff member should not have Workload
        self.assertFalse(staff.has_workload)

    @override_settings(WAM_STAFF_REGEX=None)
    @override_settings(WAM_EXTERNAL_REGEX=None)
    def test_noregex_staffuser_creates_staff(self):
        # Try with no regex, the staff object should default to internal "Staff" characteristics
        user = User.objects.create(username="staffuser", password="")
        try:
            staff = Staff.objects.get(user=user)
        except:
            staff = None

        # Check the matching staff object has been created
        self.assertIsNotNone(staff)

        # That staff member should not be External
        self.assertFalse(staff.is_external)

        # That staff member should not have Workload
        self.assertTrue(staff.has_workload)

        # Check user can still login
        self.assertTrue(user.is_active)


    @override_settings(WAM_STAFF_REGEX='^e[0-9]+$')
    @override_settings(WAM_EXTERNAL_REGEX=None)
    def test_staff_regex_only_user_creates_staff(self):
        # One user should be created as internal, the other as external
        internal_user = User.objects.create(username='e1234', password='')
        external_user = User.objects.create(username="nonstaff", password="")

        try:
            internal_staff = Staff.objects.get(user=internal_user)
        except:
            internal_staff = None

        try:
            external_staff = Staff.objects.get(user=external_user)
        except:
            external_staff = None

        # Check the matching staff objects have been created
        self.assertIsNotNone(internal_staff)
        self.assertIsNotNone(external_staff)

        # The internal staff member should not be External and have workload
        self.assertFalse(internal_staff.is_external)
        self.assertTrue(internal_staff.has_workload)
        self.assertTrue(internal_user.is_active)

        # The external staff member should be the other way around
        self.assertTrue(external_staff.is_external)
        self.assertFalse(external_staff.has_workload)
        self.assertTrue(external_user.is_active)


    @override_settings(WAM_STAFF_REGEX=None)
    @override_settings(WAM_EXTERNAL_REGEX='a[0-9]+$')
    def test_external_regex_only_user_creates_staff(self):
        # One user should be created as internal, the other as external
        internal_user = User.objects.create(username='e1234', password='')
        external_user = User.objects.create(username="a1234", password="")

        try:
            internal_staff = Staff.objects.get(user=internal_user)
        except:
            internal_staff = None

        try:
            external_staff = Staff.objects.get(user=external_user)
        except:
            external_staff = None

            # Check the matching staff objects have been created
            self.assertIsNotNone(internal_staff)
            self.assertIsNotNone(external_staff)

            # The internal staff member should not be External and have workload
            self.assertFalse(internal_staff.is_external)
            self.assertTrue(internal_staff.has_workload)
            self.assertTrue(internal_user.is_active)

            # The external staff member should be the other way around
            self.assertTrue(external_staff.is_external)
            self.assertFalse(external_staff.has_workload)
            self.assertTrue(external_user.is_active)


    @override_settings(WAM_STAFF_REGEX='e[0-9]+$')
    @override_settings(WAM_EXTERNAL_REGEX='a[0-9]+$')
    def test_both_regex_user_creates_staff(self):
        # One user should be created as internal, the other as external
        internal_user = User.objects.create(username='e1234', password='')
        external_user = User.objects.create(username="a1234", password="")
        invalid_user = User.objects.create(username='b1234', password='')

        try:
            internal_staff = Staff.objects.get(user=internal_user)
        except:
            internal_staff = None

        try:
            external_staff = Staff.objects.get(user=external_user)
        except:
            external_staff = None

        try:
            invalid_staff = Staff.objects.get(user=invalid_user)
        except:
            invalid_staff = None

        # Check the matching staff objects have been created
        self.assertIsNotNone(internal_staff)
        self.assertIsNotNone(external_staff)

        # The internal staff member should not be External and have workload
        self.assertFalse(internal_staff.is_external)
        self.assertTrue(internal_staff.has_workload)
        self.assertTrue(internal_user.is_active)

        # The external staff member should be the other way around
        self.assertTrue(external_staff.is_external)
        self.assertFalse(external_staff.has_workload)
        self.assertTrue(external_user.is_active)

        # Check the invalid user is disabled
        self.assertFalse(invalid_user.is_active)
