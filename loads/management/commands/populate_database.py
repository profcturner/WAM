"""A custom command to initially populate the database"""
# Code to implement a custom command

import random
import logging
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

from django.core.management.base import BaseCommand

# We need to manipulate User and Group Information
from django.contrib.auth.models import User, Group

# And some models
from loads.models import Category, ExternalExaminer, Activity
from loads.models import ActivityType
from loads.models import ModuleSize
from loads.models import AssessmentResourceType
from loads.models import AssessmentState
from loads.models import Campus

# And the more detailed test data
from loads.models import ActivityGenerator
from loads.models import Body
from loads.models import Module
from loads.models import ModuleStaff
from loads.models import Programme
from loads.models import Project
from loads.models import ProjectStaff
from loads.models import Staff
from loads.models import Task
from loads.models import TaskCompletion
from loads.models import WorkPackage

from WAM.settings import WAM_DEFAULT_ACTIVITY_TYPE

# Get an instance of a logger
logger = logging.getLogger(__name__)

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

        parser.add_argument('--add-test-module-allocations',
                            action='store_true',
                            dest='add-test-module-allocations',
                            default=False,
                            help='Create some sample teaching allocation')

        parser.add_argument('--add-test-project-allocations',
                            action='store_true',
                            dest='add-test-project-allocations',
                            default=False,
                            help='Create some sample project allocation')

        parser.add_argument('--add-test-task-allocations',
                            action='store_true',
                            dest='add-test-task-allocations',
                            default=False,
                            help='Create some sample task allocation')

        parser.add_argument('--test-prefix',
                            dest='test-prefix',
                            default="TEST",
                            help='This is added to usernames and groups etc. to avoid conflicts')

    def handle(self, *args, **options):
        # TODO needs some decent exception handling
        add_core_config = options['add-core-config']
        add_test_data = options['add-test-data']
        add_test_module_allocations = options['add-test-module-allocations']
        add_test_project_allocations = options['add-test-project-allocations']
        add_test_task_allocations = options['add-test-task-allocations']

        logger.info("Populate Database management command invoked.", extra={'optione': options})
        self.stdout.write('Populating data into database')

        if add_core_config:
            self.populate_basic_config(options)

        if add_test_data:
            self.populate_test_data(options)

        if add_test_module_allocations:
            self.create_module_allocations(options)

        if add_test_project_allocations:
            self.create_project_allocations(options)

        if add_test_task_allocations:
            self.create_task_allocations(options)

        if not (add_core_config or
                add_test_data or
                add_test_module_allocations or
                add_test_project_allocations or
                add_test_task_allocations):
            self.stdout.write('No option selected, use --help for more details')

        logger.info("Populate Database management command completed.")
        self.stdout.write('Complete.')


    def get_test_group_name(self, options):
        """
        Helper method to get the test group name
        :param options: the options received from the command line
        :return: the test group name
        """
        return options["test-prefix"] + " Group"


    @staticmethod
    def database_not_empty():
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
            logging.error('ERROR: Database core data not empty, quitting')
            self.stdout.write('ERROR: Database core data not empty, quitting')
            return False

        logging.info('.. Add Categories and ActivityTypes')
        if verbosity:
            self.stdout.write('.. Add Categories and ActivityTypes')
        self.add_categories_activities()

        logging.info('.. Add Module Sizes')
        if verbosity:
            self.stdout.write('.. Add Module Sizes')
        self.add_module_sizes()

        logging.info('.. Add Campuses')
        if verbosity:
            self.stdout.write('.. Add Campuses')
        self.add_campus()

        logging.info('.. Add AssessmentResourceTypes')
        if verbosity:
            self.stdout.write('.. Add AssessmentResourceTypes')
        self.add_assessment_resource_types()

        logging.info('.. Add AssessmentStates')
        if verbosity:
            self.stdout.write('.. Add AssessmentStates')
        self.add_assessment_state()

        return True


    def add_categories_activities(self):
        """Add some basic Categories and ActivityTypes"""

        admin_category = Category.objects.create(name="Administration", abbreviation="admin", colour="#00007e")
        research_category = Category.objects.create(name="Research and Impact", abbreviation="R&I", colour="#007e00")
        education_category = Category.objects.create(name="Learning and Teaching", abbreviation="L&T", colour="#7e0000")

        ActivityType.objects.create(name="Lectures and Tutorials", category=education_category)
        ActivityType.objects.create(name="General Administration", category=admin_category)
        ActivityType.objects.create(name="Faculty Committee Representation", category=admin_category)
        ActivityType.objects.create(name="Health and Safety", category=admin_category)
        ActivityType.objects.create(name="Research Administration", category=research_category)
        ActivityType.objects.create(name="Research Grant", category=research_category)
        ActivityType.objects.create(name="Teaching Administration", category=education_category)


    def add_campus(self):
        """Add a campus to be renames"""

        Campus.objects.create(name="Rename this Campus")


    def add_module_sizes(self):
        """Add some ModuleSize objects"""

        ModuleSize.objects.create(text='0 - 10', admin_scaling=0.5, assessment_scaling=0.5, order=1)
        ModuleSize.objects.create(text='11 - 20', admin_scaling=0.7, assessment_scaling=0.7, order=2)
        ModuleSize.objects.create(text='21 - 50', admin_scaling=1.0, assessment_scaling=1.0, order=3)
        ModuleSize.objects.create(text='51 - 100', admin_scaling=1.2, assessment_scaling=1.2, order=4)
        ModuleSize.objects.create(text='101 - 200', admin_scaling=1.3, assessment_scaling=1.3, order=5)
        ModuleSize.objects.create(text='200+', admin_scaling=1.4, assessment_scaling=1.4, order=6)


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
            priority=10,
            next_states_guidance="""
            As the materials have been signed off as submitted, the module moderator
            should now review the materials, and if their school policy requires it,
            upload their moderation form.<br /><br />

            If they are content that all submitted materials pass internal quality
            checks they should sign them off as accepted. Otherwise they should sign
            off that changes have been requested."""
        )

        moderated_ok_state = AssessmentState.objects.create(
            name="Moderated: Acceptance",
            description="The work has been moderated and accepted.",
            actors="moderator",
            notify="coordinator,moderator,external",
            initial_state=False,
            priority=20,
            next_states_guidance="""
            The assessment materials have now been successfully moderated. Normally an External
            Examiner should now review these in accordance with the School policy. The External
            Examiner can upload comments if so wished.<br /><br />

            If the External Examiner is content with the assessment items they can sign off their
            acceptance. Alternatively they can sign off that they would like to request some changes
            that they have detailed.<br /><br />

            <strong>Warning</strong>: while Module Coordinators can perform a final sign off they
            <strong>should not</strong> do so unless the module is not externally examined, or to
            indicate that they have received external examiner approval outside the system."""
        )

        moderated_not_ok_state = AssessmentState.objects.create(
            name="Moderated: Changes Requested",
            description="The work has been moderated but some changes are requested.",
            actors="moderator",
            notify="coordinator,moderator",
            initial_state=False,
            priority=30,
            next_states_guidance="""
            The moderator has indicated that they wish the module team to consider some changes to
            the assessment. Accordingly the module team can upload revised assessments and information
            if required.<br /><br />

            The module coordinator should then sign off that the changes have been made or to provide
            an explanation for why changes may not need to be made."""
        )

        resubmission_moderation_state = AssessmentState.objects.create(
            name="Resubmission for Moderation",
            description="Material has been resubmitted, or an explanation for the moderator given.",
            actors="coordinator",
            notify="coordinator,moderator",
            initial_state=False,
            priority=40,
            next_states_guidance="""
            The module has been resubmitted for moderation, the module moderator should now review the
            changes made, or any explanation for why changes may not be required.<br /><br />

            If they are content that all submitted materials pass internal quality checks they should
            sign them off as accepted. Otherwise they should sign off that changes have again been requested.
            """
        )

        external_ok_state = AssessmentState.objects.create(
            name="External Examination: Acceptance",
            description="The work has been externally examined and accepted.",
            actors="external",
            notify="coordinator,moderator,external,assessment_team",
            initial_state=False,
            priority=50,
            next_states_guidance="""
            The external examiner has accepted that the module materials are appropriate and have been
            accepted.<br /><br />

            The final responsibility for signing off all materials rests with the module coordinator.
            """
        )

        external_not_ok_state = AssessmentState.objects.create(
            name="External Examination: Changes Requested",
            description="The work has been moderated but some changes are requested.",
            actors="external",
            notify="coordinator,moderator,external",
            initial_state=False,
            priority=60,
            next_states_guidance="""
            The external examiner has indicated that they wish the module team to consider some changes
            to the assessment. Accordingly the module team can upload revised assessments and information
            if required.<br /><br />

            The module coordinator should then sign off that the changes have been made or to provide
            an explanation for why changes may not need to be made.
            """
        )

        resubmission_external_state = AssessmentState.objects.create(
            name="Resubmission for External Examiner",
            description="Material has been resubmitted, or an explanation for the moderator given.",
            actors="coordinator",
            notify="coordinator,external",
            initial_state=False,
            priority=70,
            next_states_guidance="""
            The module has been resubmitted for external examination, the external examiner should now
            review the changes made, or any explanation for why changes may not be required.<br /><br />

            If they are content that all submitted materials pass internal quality checks they should
            sign them off as accepted. Otherwise they should sign off that changes have again been requested.
            """
        )

        coordinator_final_state = AssessmentState.objects.create(
            name="Coordinator Final Sign-off",
            description="The coordinator confirms all materials are final and complete.",
            actors="coordinator",
            notify="coordinator,assessment_staff",
            initial_state=False,
            priority=80,
            next_states_guidance="""
            The materials for the module have been finally signed off. It is still possible to upload
            new materials and restart the process if required.
            """
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

        # Make a very naive check that some initial configuration exists
        # This can happen if people haven't added basic config yet.
        if(Campus.objects.count() == 0):
            logging.error("There seems to be no basic schema")
            logging.error("Did you mean to use --add-core-config first?")
            self.stderr.write("ERROR: There seems to be no basic schema")
            self.stderr.write("ERROR: Did you mean to use --add-core-config first?")
            return False

        # Create the WorkPackage first
        package = self.create_work_package(options)

        if not package:
            self.stderr.write("ERROR: Unable to continue")
            return False

        # Then the Staff
        self.create_staff(package, options)

        # Then the External Examiners
        self.create_externals(package, options)

        # Then Programmes
        self.create_programmes(package, options)

        # The Modules
        self.create_modules(package, options)

        # The Generators
        self.create_generators(package, options)

        return True


    def create_work_package(self, options):
        """Create an test work package"""

        test_prefix = options['test-prefix']
        verbosity = options['verbosity']

        # Create a Group
        group_name = self.get_test_group_name(options)

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
            enddate=date.today() + timedelta(days=364),
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

            # Tweak the autocreated corresponding staff objects
            staff = Staff.objects.get(user=user)
            staff.fte = random.choice([100] * 10 + [50] * 2 + [60] + [40])
            staff.title = title
            staff.staff_number = username
            staff.package = package
            staff.is_external = False
            staff.has_workload = True
            staff.save()

            # Add the user to a group as well
            group = random.choice(groups)
            group.user_set.add(user)

            # A different username for the next one
            username_number += 1


    def get_external_names(self):
        """Define names for external examiners"""

        # It's only a joke...
        external_names = [
            ("Dr", "Victor", "von Doom"),
            ("Dr", "Otto", "Octavius")
        ]

        return external_names


    def create_externals(self, package, options):
        """Create the external objects as above and set their WorkPackage"""

        test_prefix = options['test-prefix']
        verbosity = options['verbosity']

        # Set up an initial username
        username_number = 1000

        # Loop through all the sample data above
        for (title, first_name, last_name) in self.get_external_names():
            if verbosity:
                self.stdout.write(".. Creating External: {} {} {}".format(title, first_name, last_name))

            username = test_prefix + "ext" + str(username_number)

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

            # Tweak the autocreated corresponding staff objects
            staff = Staff.objects.get(user=user)
            staff.fte = random.choice([100] * 10 + [50] * 2 + [60] + [40])
            staff.title = title
            staff.staff_number = username
            staff.package = package
            staff.is_external = True
            staff.has_workload = False
            staff.save()

            # A different username for the next one
            username_number += 1


    def get_programme_names(self):
        """Some basic programmes"""

        programme_names = [
            ('1000', 'BSc Hons Guided Mutations'),
            ('1001', 'MSc Hons Avenging Justice Fundamentals'),
            ('1002', 'MEng Hons Terran and Asgardian Technology')
        ]

        return programme_names


    def create_programmes(self, package, options):
        """Create some programmes and add them to a package"""

        verbosity = options['verbosity']

        externals = list(Staff.objects.all().filter(package=package).filter(is_external=True))

        for (programme_code, programme_name) in self.get_programme_names():
            if verbosity:
                self.stdout.write(".. Creating Programme: {} {}".format(programme_code, programme_name))
            programme = Programme.objects.create(
                programme_code=programme_code,
                programme_name=programme_name,
                package=package,
            )

            programme.examiners.add(random.choice(externals))


    def get_module_names(self):
        """Some basic module names"""

        module_names = [
            ('X101', 'The Human Genome'),
            ('X102', 'Controlling Mutation'),
            ('X103', 'Extinction Level Events and How to Avoid Them'),
            ('J101', 'Justice Fundamentals'),
            ('J102', 'Avenging Fundamentals'),
            ('J103', 'Planning to Take Down Your Rogue Friends'),
            ('J104', 'Building Defensive Technology'),
            ('A101', 'Arc Reactor Technology'),
            ('A102', 'Murder Bot Fundamentals, the Lessons of Ultron'),
            ('A103', 'Nanotechnology Armour Basics'),
            ('A104', 'Kryptonian and Asgardian Physiology'),
            ('A105', 'The Sokovia Accords')
        ]

        return module_names


    def create_modules(self, package, options):
        """Create the modules"""

        verbosity = options['verbosity']

        # Get some of the other data
        campuses = list(Campus.objects.all())
        module_sizes = list(ModuleSize.objects.all())
        programmes = list(Programme.objects.all().filter(package=package))
        staff = list(Staff.objects.all().filter(package=package))

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

    def get_generator_data(self):
        """
        Some generator data
        """

        generator_data = [
            ("Research Tasks", ActivityGenerator.PERCENTAGE, 0, 40, "1,2,3")
        ]

        return generator_data


    def create_generators(self, package, options):
        """
        Create some ActivityGenerators for the test work package

        :param package:     the package created for test data
        :param options:     the options for the management command
        """

        test_prefix = options['test-prefix']
        verbosity = options['verbosity']

        test_group_name = self.get_test_group_name(options)

        test_group = Group.objects.get(name=test_group_name)
        if not test_group:
            message = "Cannot find the test group"
            self.stdout.write(self.style.ERROR(message))
            logger.error(message)
            return

        research_activity = ActivityType.objects.get(name="Research Administration")
        if not research_activity:
            message = "Cannot find a research administration activity type"
            self.stdout.write(self.style.ERROR(message))
            logger.error(message)
            return

        generator_data = self.get_generator_data()
        for name, hours_percentage, hours, percentage, semesters in generator_data:
            if verbosity:
                self.stdout.write(".. Creating Generator {}".format(name))
            generator = ActivityGenerator.objects.create(
                name = name,
                hours_percentage = hours_percentage,
                hours = hours,
                percentage = percentage,
                semester = semesters,
                activity_type = research_activity,
                package = package,
            )

            # Assign the whole group
            generator.groups.add(test_group)
            generator.save()


    def create_module_allocations(self, options):
        """
        Create some allocations for the staff in the package, for about half the modules.

        These will be somewhat random and will attempt to create some under and over allocations.

        :param options: the main options into the command
        """

        test_prefix = options['test-prefix']
        verbosity = options['verbosity']

        # Check some Staff exist
        if not Staff.objects.count():
            message = "Cannot find any staff in the package, did you mean to run --add-test-data first?"
            self.stdout.write(self.style.ERROR(message))
            logger.error(message)
            return

        # And now grab the Work Package
        package_name = test_prefix + " Work Package"
        package = WorkPackage.objects.get(name=package_name)

        if not package:
            message = "Cannot find Work Package {}, cannot make allocations".format(package_name)
            logger.error(message)
            self.stdout.write(message)
            return

        message = 'Creating module allocations for {}'.format(package)
        logger.info(message)
        if verbosity:
            self.stdout.write(message)

        default_activity_type = ActivityType.objects.get(pk=WAM_DEFAULT_ACTIVITY_TYPE)
        if not default_activity_type:
            message = 'No activity for WAM_DEFAULT_ACTIVITY_TYPE found for'
            logger.error(message)
            self.stdout.write(message)
            return

        # Get the modules in the package, and any staff currently configured for that package
        modules = list(Module.objects.all().filter(package=package))
        staff = list(Staff.objects.all().filter(package=package))
        proportion_choices = [25, 30, 40, 50, 55, 75, 100]
        allocation_limit_choices = [80, 100, 120]

        # Let's create allocations for half of these (rounded)
        modules_to_allocate = int(len(modules)/2)
        logger.debug("attempt to allocate {} modules".format(modules_to_allocate))

        allocated_modules = []
        for i in range(modules_to_allocate):
            # Grab a module not already picked
            module = random.choice([item for item in modules if item not in allocated_modules])
            if ModuleStaff.objects.filter(module=module).count():
                logger.warning("Skipping already allocated module: {}".format(module))
                continue

            allocated_modules.append(module)

            allocated_staff = []
            allocation_so_far = 0
            allocation_limit = random.choice(allocation_limit_choices)
            while allocation_so_far < allocation_limit:
                # Make a choice of how much in this slice
                proportion = random.choice(proportion_choices)
                # But scale it to a maximum of the limits above.
                if allocation_so_far + proportion > allocation_limit:
                    proportion = allocation_limit - allocation_so_far
                # And someone not allocated to this module
                staff_member = random.choice([item for item in staff if item not in allocated_staff])
                allocated_staff.append(staff_member)

                ModuleStaff.objects.create(
                    module=module,
                    staff=staff_member,
                    package=package,
                    activity_type=default_activity_type,
                    contact_proportion=proportion,
                    admin_proportion=proportion,
                    assessment_proportion=proportion,
                )
                logger.info(".. allocated {}% to staff member {} on module {}".format(proportion, staff, module))
                allocation_so_far += proportion

            message = "Allocations made to module {}".format(module)
            logger.info(message)
            if(verbosity):
                self.stdout.write(message)


    def get_tasks(self):
        """
        Some basic data for Tasks we shall create


        :return:
        """

        task_data = [
            ('Sign Sokovia Accords', """We are all required to sign the Sokovia Accords by the assigned deadline. See https://en.wikipedia.org/wiki/Features_of_the_Marvel_Cinematic_Universe#Sokovia_Accords for more details."""),
            ('Set Exam Papers', """Please set your exam papers by the specified deadline"""),
            ('Peer Support Review',
             """
             Please ensure you have completed your PSR by the appropriate deadline""")
        ]
        return task_data


    def create_task_allocations(self, options):
        """
        Create some Tasks with some random targets from test data

        :param options: the main options into the command
        """

        test_prefix = options['test-prefix']
        verbosity = options['verbosity']

        # Check some Staff exist
        if not Staff.objects.count():
            message = "Cannot find any staff in the package, did you mean to run --add-test-data first?"
            self.stdout.write(self.style.ERROR(message))
            logger.error(message)
            return

        # And now grab the group name
        group_name = self.get_test_group_name(options)
        group = Group.objects.get(name=group_name)

        if not group:
            message = "Cannot find Group {}, cannot make tasks".format(group_name)
            logger.error(message)
            self.stdout.write(message)
            return

        message = 'Creating task allocations for {}'.format(group)
        logger.info(message)
        if verbosity:
            self.stdout.write(message)

        categories = Category.objects.all()
        task_data = self.get_tasks()
        deadline = datetime.now() + timedelta(days=6)

        for name, details in task_data:
            task = Task.objects.create(
                name = name,
                details = details,
                category = random.choice(categories),
                deadline = deadline,
            )
            deadline += timedelta(days=20)
            task.groups.add(group)
            task.save()

        message = "allocations made to group {}".format(group)
        logger.info(message)
        if(verbosity):
            self.stdout.write(message)


    def create_project_allocations(self, options):
        """
        Create a Body, a Project and some ProjectStaff allocations for testing purposes

        The Project should begin 6 months ago, and end 36 months in the future
        Staff will be somewhat randomly allocated.

        :param options: the main options into the command
        """

        test_prefix = options['test-prefix']
        verbosity = options['verbosity']

        # Check some Staff exist
        if not Staff.objects.count():
            message = "Cannot find any staff in the package, did you mean to run --add-test-data first?"
            self.stdout.write(self.style.ERROR(message))
            logger.error(message)
            return


        # And now grab the Work Package
        package_name = test_prefix + " Work Package"
        package = WorkPackage.objects.get(name=package_name)

        if not package:
            message = "Cannot find Work Package {}, cannot make allocations".format(package_name)
            logger.error(message)
            self.stdout.write(message)
            return

        message = 'Creating project allocations for {}'.format(package)
        logger.info(message)
        if verbosity:
            self.stdout.write(message)

        research_activity = ActivityType.objects.get(name="Research Administration")
        if not research_activity:
            message = "Cannot find a research administration activity type"
            self.stdout.write(self.style.ERROR(message))
            logger.error(message)
            return

        try:
            shield = Body.objects.get(name="S.H.I.E.L.D.")
        except Body.DoesNotExist:
            shield = Body.objects.create(
                name="S.H.I.E.L.D.",
                details="Earth Security Funding",
            )

        project_start = date.today() + relativedelta(months=-6)
        project_end = date.today() + relativedelta(months=+36)

        project = Project.objects.create(
            name = "Watchtower Initiative, Low Earth Orbit",
            start = project_start,
            end = project_end,
            body = shield,
            activity_type = research_activity,
        )

        # Make some random project allocations
        staff = list(Staff.objects.all().filter(package=package))
        hours_per_week= [2, 3, 5, 10]

        # Let's create allocations for five staff
        staff_to_allocate = 5
        logger.debug("attempt to allocate {} staff members to project".format(staff_to_allocate))

        allocated_staff = []
        for i in range(staff_to_allocate):
            # Grab a module not already picked
            staff_member = random.choice([item for item in staff if item not in allocated_staff])
            ProjectStaff.objects.create(
                project = project,
                staff = staff_member,
                start = project_start,
                end = project_end,
                hours_per_week = random.choice(hours_per_week),
            )
            allocated_staff.append(staff_member)

        message = "allocations made to project {}".format(project)
        logger.info(message)
        if(verbosity):
            self.stdout.write(message)

