'''A custom command to initially populate the database'''
# Code to implement a custom command

import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

# We need to manipulate User and Group Information
from django.contrib.auth.models import User, Group

# We will be using mail functionality, and templates to create them
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.template import Context

# And some models
from loads.models import Category
from loads.models import ActivityType
from loads.models import ModuleSize
from loads.models import AssessmentResourceType
from loads.models import AssessmentState
from loads.models import Campus

# And the more detailed test data
from loads.models import Staff
from loads.models import Programme
from loads.models import Module
from loads.models import WorkPackage

# We need to access a few settings
from django.conf import settings

class Command(BaseCommand):
    help = 'Initially populate a database with defaults, and optionally, test data'

    def add_arguments(self, parser):
        parser.add_argument('--add-core-config',
            action='store_true',
            dest='add-core-config',
            default=False,
            help='Add core configuration data')

        parser.add_argument('--add-test-data',
            action='store_true',
            dest='add-test-data',
            default=False,
            help='Don\'t just add initial basics, but test data for testing and training')

        parser.add_argument('--test-prefix',
            dest='test-prefix',
            default="TEST",
            help='This is added to usernames and groups etc. to avoid conflicts')

            
    def handle(self, *args, **options):
        #TODO needs some decent exception handling
        verbosity = options['verbosity']
        add_core_config = options['add-core-config']
        add_test_data = options['add-test-data']
        

        self.stdout.write('Populating data into database')

        if add_core_config:
            self.populate_basic_config(options)

        if add_test_data:
            self.populate_test_data(options)

        if not (add_core_config or add_test_data):
            self.stdout.write('No option selected, use --help for more details')

        self.stdout.write('Complete.')


    def database_not_empty(self):
        """Check if any data is already there"""

        if Category.objects.all().count():
            return True

        if ActivityType.objects.all().count():
            return True

        if ModuleSize.objects.all().count():
            return True

        if AssessmentResourceType.objects.all().count():
            return True

        if AssessmentState.objects.all().count():
            return True

        if Campus.objects.all().count():
            return True

        # We don't check anything else for now, maybe we should, but these items would be needed to have much else
        return False


    def populate_basic_config(self, options):
        """Add the basic configuration required to get going"""

        verbosity = options['verbosity']

        if self.database_not_empty():
            self.stdout.write('ERROR: Database core data not empty, quitting')
            return

        if verbosity:
            self.stdout.write('.. Add Categories and ActivityTypes')
        self.add_categories_activities()

        if verbosity:
            self.stdout.write('.. Add Module Sizes')
        self.add_module_sizes()

        if verbosity:
            self.stdout.write('.. Add Campuses')
        self.add_campus()

        if verbosity:
            self.stdout.write('.. Add AssessmentResourceTypes')
        self.add_assessment_resource_types()

        if verbosity:
            self.stdout.write('.. Add AssessmentStates')
        self.add_assessment_state()


    def add_categories_activities(self):
        """Add some basic Categories and ActivityTypes"""

        admin_category = Category.objects.create(name="Administration")
        research_category = Category.objects.create(name="Research and Impact")
        education_category = Category.objects.create(name="Learning and Teaching")

        ActivityType.objects.create(name="General Administration", category=admin_category)
        ActivityType.objects.create(name="Faculty Committee Representation", category=admin_category)
        ActivityType.objects.create(name="Health and Safety", category=admin_category)
        ActivityType.objects.create(name="Lectures and Tutorials", category=education_category)
        ActivityType.objects.create(name="Research Administration", category=research_category)
        ActivityType.objects.create(name="Research Grant", category=research_category)
        ActivityType.objects.create(name="Teaching Administration", category=education_category)


    def add_campus(self):
        """Add a campus to be renames"""

        Campus.objects.create(name="Rename this Campus")


    def add_module_sizes(self):
        """Add some ModuleSize objects"""

        ModuleSize.objects.create(text='0 - 10', admin_scaling=0.5, assessment_scaling=0.5)
        ModuleSize.objects.create(text='11 - 20', admin_scaling=0.7, assessment_scaling=0.7)
        ModuleSize.objects.create(text='20 - 50', admin_scaling=1.0, assessment_scaling=1.0)
        ModuleSize.objects.create(text='50 - 100', admin_scaling=1.2, assessment_scaling=1.2)
        ModuleSize.objects.create(text='100 - 200', admin_scaling=1.3, assessment_scaling=1.3)
        ModuleSize.objects.create(text='200+', admin_scaling=1.4, assessment_scaling=1.4)


    def add_assessment_resource_types(self):
        """Add some sensible AssessmentResourceTypes"""

        AssessmentResourceType.objects.create(name="Exam Paper")
        AssessmentResourceType.objects.create(name="Coursework Brief")
        AssessmentResourceType.objects.create(name="Exam Solution")
        AssessmentResourceType.objects.create(name="Coursework Solution")
        AssessmentResourceType.objects.create(name="Moderation")
        AssessmentResourceType.objects.create(name="External Comment")
        AssessmentResourceType.objects.create(name="Comment")


    def add_assessment_state(self):
        """Add a basic AssessmentState workflow"""

        # Add the states first, we can't add all links till they are there

        initial_state = AssessmentState.objects.create(
            name="Initial Submission",
            description="The initial submission of exams and/or coursework.",
            actors="coordinator",
            notify="coordinator,moderator",
            initial_state=True,
            priority=10
        )

        moderated_ok_state = AssessmentState.objects.create(
            name="Moderated: Acceptance",
            description="The work has been moderated and accepted.",
            actors="moderator",
            notify="coordinator,moderator,external",
            initial_state=False,
            priority=20
        )

        moderated_not_ok_state = AssessmentState.objects.create(
            name="Moderated: Changes Requested",
            description="The work has been moderated but some changes are requested.",
            actors="moderator",
            notify="coordinator,moderator",
            initial_state=False,
            priority=30
        )

        resubmission_moderation_state = AssessmentState.objects.create(
            name="Resubmission for Moderation",
            description="Material has been resubmitted, or an explanation for the moderator given.",
            actors="coordinator",
            notify="coordinator,moderator",
            initial_state=False,
            priority=40
        )

        external_ok_state = AssessmentState.objects.create(
            name="External Examination: Acceptance",
            description="The work has been externally examined and accepted.",
            actors="external",
            notify="coordinator,moderator,external,assessment_team",
            initial_state=False,
            priority=50
        )

        external_not_ok_state = AssessmentState.objects.create(
            name="External Examination: Changes Requested",
            description="The work has been moderated but some changes are requested.",
            actors="external",
            notify="coordinator,moderator,external",
            initial_state=False,
            priority=60
        )

        resubmission_external_state = AssessmentState.objects.create(
            name="Resubmission for External Examiner",
            description="Material has been resubmitted, or an explanation for the moderator given.",
            actors="coordinator",
            notify="coordinator,external",
            initial_state=False,
            priority=70
        )

        coordinator_final_state = AssessmentState.objects.create(
            name="Coordinator Final Sign-off",
            description="The coordinator confirms all materials are final and complete.",
            actors="coordinator",
            notify="coordinator,assessment_staff",
            initial_state=False,
            priority=80
        )

        # Now make links

        coordinator_final_state.next_states.add(initial_state)

        resubmission_external_state.next_states.add(external_not_ok_state)
        resubmission_external_state.next_states.add(external_ok_state)
        resubmission_external_state.next_states.add(coordinator_final_state)

        external_not_ok_state.next_states.add(resubmission_external_state)

        external_ok_state.next_states.add(coordinator_final_state)

        resubmission_moderation_state.next_states.add(moderated_ok_state)
        resubmission_moderation_state.next_states.add(moderated_not_ok_state)

        moderated_not_ok_state.next_states.add(resubmission_moderation_state)

        moderated_ok_state.next_states.add(external_ok_state)
        moderated_ok_state.next_states.add(external_not_ok_state)
        moderated_ok_state.next_states.add(coordinator_final_state)

        initial_state.next_states.add(moderated_ok_state)
        initial_state.next_states.add(moderated_not_ok_state)


    def populate_test_data(self, options):
        """Add users, modules and programmes etc."""

        # Create the WorkPackage first
        package = self.create_work_package(options)

        if not package:
            self.stderr.write("ERROR: Unable to continue")
            return

        # Then the Staff
        self.create_staff(package, options)

        # Then Programmes
        self.create_programmes(package, options)

        # The Modules
        self.create_modules(package, options)



    def create_work_package(self, options):
        """Create an test work package"""

        test_prefix = options['test-prefix']
        verbosity = options['verbosity']

        # Create a Group
        group_name = test_prefix + " Group"
        if verbosity:
            self.stdout.write('.. Creating User Group: {}'.format(group_name))

        if Group.objects.all().filter(name=group_name).count():
            # There's already a group of this name

            self.stderr.write('ERROR: Group already exists.')
            return None
        else:
            group = Group.objects.create(
                name=group_name
            )

        # And now a Work Package
        package_name = test_prefix + " Work Package"
        if verbosity:
            self.stdout.write('.. Creating Work Package: {}'.format(package_name))

        if WorkPackage.objects.all().filter(name=package_name).count():
            # There's already a package of this name
            self.stderr.write('ERROR: WorkPackage already exists.')
            return None

        package = WorkPackage.objects.create(
            name=test_prefix + " Work Package",
            details="This is for testing and training",
            startdate=date.today(),
            enddate=date.today()+timedelta(days=364),
            hidden=True,
            draft=True,
        )

        # Add the group to the package
        package.groups.add(group)

        return package


    def get_staff_names(self):
        """Return a list of tuples with some test staff names"""

        staff_names = [
            ('Professor', 'Charles', 'Xavier'),
            ('Professor', 'Carol', 'Danvers'),
            ('Professor', 'Clark', 'Kent'),
            ('Professor', 'Diana', 'Prince'),
            ('Dr', 'Bruce', 'Banner'),
            ('Ms', 'Natasha', 'Romanov'),
            ('Dr', 'Bruce', 'Wayne'),
            ('Dr', 'Ororo', 'Munroe'),
            ('Mr', 'James', 'Howlett'),
            ('Professor', 'Jean', 'Gray'),
            ('Dr', 'Tony', 'Stark'),
            ('Dr', 'Riri', 'Williams'),
            ('Dr', 'Scott', 'Summers'),
            ('Dr', 'Wanda', 'Maximoff'),
            ('Mr', 'Wade', 'Wilson'),
            ('Ms', 'Pepper', 'Potts'),
            ('Mr', 'Peter', 'Parker'),
            ('Ms', 'Maria', 'Hill'),
            ('Mr', 'T\'Challa', 'Udaku'),
            ('Ms', 'Selena', 'Kyle')
        ]

        return staff_names


    def create_staff(self, package, options):
        """Create the staff objects as above and add them to a WorkPackage"""

        test_prefix = options['test-prefix']
        verbosity = options['verbosity']

        # Get all the groups in the package
        groups = list(package.groups.all())

        # Set up an initial username
        username_number = 1000

        # Loop through all the sample data above
        for (title, first_name, last_name) in self.get_staff_names():
            if verbosity:
                self.stdout.write(".. Creating Staff: {} {} {}".format(title, first_name, last_name))

            username = test_prefix + str(username_number)

            if User.objects.all().filter(username=username):
                self.stderr.write("ERROR: user already exists")
                continue

            if Staff.objects.all().filter(staff_number=username):
                self.stderr.write("ERROR: staff number already in user")
                continue

            user = User.objects.create(
                username=username,
                email="invalid@invalid.com",
                password="invalid",
                first_name=first_name,
                last_name=last_name)

            # We don't want these people to be able to login!
            user.set_unusable_password()
            user.save()

            # Create the linked staff objects
            staff = Staff.objects.create(
                user=user,
                title=title,
                staff_number=username,
                package=package
            )

            # Add the user to a group as well
            group = random.choice(groups)
            group.user_set.add(user)

            # A different username for the next one
            username_number += 1


    def get_programme_names(self):
        """Some basic programmes"""

        programme_names = [
            ('1000', 'BSc Hons Guided Mutations'),
            ('1001', 'MSc Hons Avenging Justice Fundamentals')
        ]

        return programme_names


    def create_programmes(self, package, options):
        """Create some programmes and add them to a package"""

        verbosity = options['verbosity']

        for (programme_code, programme_name) in self.get_programme_names():
            if verbosity:
                self.stdout.write(".. Creating Programme: {} {}".format(programme_code, programme_name))
            Programme.objects.create(
                programme_code=programme_code,
                programme_name=programme_name,
                package=package
            )


    def get_module_names(self):
        """Some basic module names"""

        module_names = [
            ('X101', 'The Human Genome'),
            ('X102', 'Controlling Mutation'),
            ('X103', 'Extinction Level Events and How to Avoid Them'),
            ('J101', 'Justice Fundamentals'),
            ('J102', 'Avenging Fundamentals'),
            ('J103', 'Planning to Take Down Your Rogue Friends'),
            ('J104', 'Building defensive technology')
        ]

        return module_names


    def create_modules(self, package, options):
        """Create the modules"""

        verbosity = options['verbosity']

        # Get some of the other data
        campuses = list(Campus.objects.all())
        module_sizes = list(ModuleSize.objects.all())
        programmes = list(Programme.objects.all().filter(package=package))
        staff = list(Staff.objects.all())

        for (module_code, module_name) in self.get_module_names():
            if verbosity:
                self.stdout.write(".. Creating Module {} {}".format(module_code, module_name))
            module = Module.objects.create(
                module_code=module_code,
                module_name=module_name,
                campus=random.choice(campuses),
                semester=random.choice([1, 2, 3]),
                credits=20,
                contact_hours=random.choice([36, 48, 60]),
                size=random.choice(module_sizes),
                lead_programme=random.choice(programmes),
                coordinator=random.choice(staff),
                package=package
            )

            # Let's add a moderator who isn't the coordinator
            moderator = module.coordinator
            while moderator is module.coordinator:
                moderator = random.choice(staff)
            module.moderators.add(moderator)

            # Finally add the module to the lead_programme in the list of programmes
            module.programmes.add(module.lead_programme)



