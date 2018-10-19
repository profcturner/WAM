from django.test import TestCase
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
        coordinator = Staff.objects.create(user=user_aA)
        team_member = Staff.objects.create(user=user_aB)
        resource_owner = Staff.objects.create(user=user_aC)
        moderator = Staff.objects.create(user=user_aD)
        other_staff = Staff.objects.create(user=user_aE)

        assessment_staff = Staff.objects.create(user=user_aF)

        lead_examiner = ExternalExaminer.objects.create(user=user_eA)
        associated_examiner = ExternalExaminer.objects.create(user=user_eB)
        other_examiner = ExternalExaminer.objects.create(user=user_eC)

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


class AssessmentResourceTestCase(TestCase):
    def setUp(self):
        # Create a workpackage
        package = WorkPackage.objects.create(name="test", startdate="2017-09-01", enddate="2018-08-31")

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
        coordinator = Staff.objects.create(user=user_aA)
        team_member = Staff.objects.create(user=user_aB)
        resource_owner = Staff.objects.create(user=user_aC)
        moderator = Staff.objects.create(user=user_aD)
        other_staff = Staff.objects.create(user=user_aE)

        assessment_staff = Staff.objects.create(user=user_aF)

        lead_examiner = ExternalExaminer.objects.create(user=user_eA)
        associated_examiner = ExternalExaminer.objects.create(user=user_eB)
        other_examiner = ExternalExaminer.objects.create(user=user_eC)

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
        lead_examiner = ExternalExaminer.objects.get(user__username="externalA")
        resource = AssessmentResource.objects.get(name="test")

        # Lead Examiners should be able to download
        self.assertEqual(resource.is_downloadable_by(lead_examiner), True)
        self.assertEqual(resource.is_downloadable_by_staff(lead_examiner), False)
        self.assertEqual(resource.is_downloadable_by_external(lead_examiner), True)

    def test_resource_associate_examiner_permissions(self):
        associate_examiner = ExternalExaminer.objects.get(user__username="externalB")
        resource = AssessmentResource.objects.get(name="test")

        # Lead Examiners should be able to download
        self.assertEqual(resource.is_downloadable_by(associate_examiner), True)
        self.assertEqual(resource.is_downloadable_by_staff(associate_examiner), False)
        self.assertEqual(resource.is_downloadable_by_external(associate_examiner), True)

    def test_resource_other_examiner_permissions(self):
        other_examiner = ExternalExaminer.objects.get(user__username="externalC")
        resource = AssessmentResource.objects.get(name="test")

        # Other Examiners should not be able to download
        self.assertEqual(resource.is_downloadable_by(other_examiner), False)
        self.assertEqual(resource.is_downloadable_by_staff(other_examiner), False)
        self.assertEqual(resource.is_downloadable_by_external(other_examiner), False)
