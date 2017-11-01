from django.test import TestCase

# Import Some Django models that we use

from django.contrib.auth.models import User, Group

# Import some models

from .models import ActivityGenerator
from .models import AssessmentResource
from .models import AssessmentResourceType
from .models import AssessmentStaff
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
from .models import ExamTracker
from .models import CourseworkTracker
from .models import Project
from .models import ProjectStaff
from .models import WorkPackage


class AssessmentResourceTestCase(TestCase):
    def setUp(self):
        # Create a workpackage
        package = WorkPackage.objects.create(name="test", startdate="2017-09-01", enddate="2018-08-31")
        
        # Create a campus
        campus = Campus.objects.create(name="campus")
        
        # Create a Module Size
        modulesize = ModuleSize.objects.create(text="50", admin_scaling=1.0, assessment_scaling=1.0)
                
        # Create some Users
        user_aA = User.objects.create(username="academicA")
        user_aB = User.objects.create(username="academicB")
        user_aC = User.objects.create(username="academicC")
        user_aD = User.objects.create(username="academicD")
        user_aE = User.objects.create(username="academicE")
        
        user_eA = User.objects.create(username="externalA")
        user_eB = User.objects.create(username="externalB")
        user_eC = User.objects.create(username="externalC")

        # Create linked Staff and ExternalExaminers
        coordinator = Staff.objects.create(user=user_aA)
        team_member = Staff.objects.create(user=user_aB)
        resource_owner = Staff.objects.create(user=user_aC)
        moderator = Staff.objects.create(user=user_aD)
        other_staff = Staff.objects.create(user=user_aE)
        
        lead_examiner = ExternalExaminer.objects.create(user=user_eA)
        associated_examiner = ExternalExaminer.objects.create(user=user_eB)
        other_examiner = ExternalExaminer.objects.create(user=user_eC)

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
                

