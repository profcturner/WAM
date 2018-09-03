"""Django Models for WAM project"""

import datetime

from django.db import models
from django.contrib.auth.models import User, Group

from django.core.validators import validate_comma_separated_integer_list

# code to handle timezones
from django.utils.timezone import utc

# TODO: Needs more elegant handling than this
# This is actually deprecated and will be removed at some point
ACADEMIC_YEAR = '2016/2017'


def divide_by_semesters(total_hours, semester_string):
    """divide hours equally between targeted semesters

    total_hours     the total number of hours to divide
    semester_string comma separated list of semesters the hours are in

    returns a list with the first item containing the total and
    then each following item being the hours for that semester
    """
    semesters = semester_string.split(',')

    # Create a list to contain their subdivision
    split_hours = list()
    # How many semesters are listed?
    no_semesters = len(semesters)
    # We currently have three semesters, 1, 2 and 3
    for semester in range(1, 4):
        # Check if this one is flagged, brutally ugly code :-(
        # TODO: Try and fix the abomination
        if semester_string.count(str(semester)) > 0:
            split_hours.append(total_hours / no_semesters)
        else:
            # Nothing in this semester
            split_hours.append(0)

    split_hours.insert(0, total_hours)
    return split_hours


class WorkPackage(models.Model):
    """Groups workload by user groups and time

    A WorkPackage can represent all the users and the time period
    for which activities are relevant. A most usual application
    would be to group activities by School and Academic Year.

    name        the name of the package, probably the academic unit
    details     any further details of the package
    startdate   the first date of activities related to the package
    enddate     the end date of the activities related to the package
    draft       indicates the package is still being constructed
    archive     indicates the package is maintained for record only
    groups      a collection of all django groups affected for workload
    created     when the package was created
    modified    when the package was last modified
    nominal_hours
                the considered normal number of load hours in a year
    credit_contact_scaling
                multiplier from credit points to contact hours
    contact_admin_scaling
                multiplier from contact hours to admin hours
    contact_assessment_scaling
                multiplier from contact hours to assessment hours
    working_days
                the expected working days in the package (i.e. leaving out leave)
    days_in_week
                the number of working days in a week (usually 5)
    contact_formula
                a formula for calculating unspecified contact hours
    admin_formula
                a formula for calculating unspecified admin hours
    assessment_formula
                a formula for calculating unspecified assessment hours
    """

    # TODO: create sensible defaults for formulae below and then enable
    name = models.CharField(max_length=100)
    details = models.TextField()
    startdate = models.DateField()
    enddate = models.DateField()
    draft = models.BooleanField(default=True)
    archive = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)
    groups = models.ManyToManyField(Group, blank=True)
    nominal_hours = models.PositiveIntegerField(default=1600)
    credit_contact_scaling = models.FloatField(default=8 / 20)
    contact_admin_scaling = models.FloatField(default=1)
    contact_assessment_scaling = models.FloatField(default=1)
    working_days = models.PositiveIntegerField(default=228)
    days_in_week = models.PositiveIntegerField(default=5)
    # contact_formula = models.TextField()
    # admin_formula = models.TextField()
    # assessment_formula = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name + ' (' + str(self.startdate) + ' - ' + str(self.enddate) + ')'

    def __clone_programmes(self, source_package, options, messages):
        """Clones programmes from source package and produces a mapping for other operations

        See clone_from() for details and documentation."""

        messages.append(("Information", "Cloning and mapping Programmes", ""))
        # Get all the programmes
        programmes = Programme.objects.all().filter(package=source_package)
        # Create a mapping dict
        mapping_programmes = dict()

        for programme in programmes:
            # Remember the original primary key
            original_pk = programme.pk
            # Now invalidate it
            programme.pk = None
            # And now point to the new package
            programme.package = self
            # And force a save to create a new object
            programme.save()
            # Record the mapping from the old programme to the new
            mapping_programmes.update({original_pk: programme.pk})

        return mapping_programmes


    def __clone_activity_sets(self, source_package, options, messages):
        """Copies relevant activity sets with a mapping

        See clone_from() for details and documentation.

        Determines the activity sets in use in an existing package and
        copies non project sets for the new package. A mapping from the
        old primary keys to the new keys is returned in a dictionary.
        """

        messages.append(("Information", "Cloning and Mapping Activity Sets", ""))
        # Get all activities in the package that belong to an Activity Set
        activities = Activity.objects.all().filter(package=source_package).filter(activity_set__isnull=False)
        # Create a mapping dict
        mapping_activity_set = dict()

        for activity in activities:
            activity_set = activity.activity_set
            # We ignore project based sets, they should be generated freshly, not copied
            if activity_set.project:
                continue
            # Have we already mapped this one?
            if activity_set.pk in mapping_activity_set:
                continue

            # Ok, it's new. Get the existing primary key
            original_pk = activity_set.pk
            # Remember we cloned it
            messages.append(("Cloned", "Activity Set", str(activity_set)))
            # Reset the pk and save a copy
            activity_set.pk = None
            activity_set.save()
            # Record the mapping
            mapping_activity_set.update({original_pk: activity_set.pk})

        return mapping_activity_set

    def __clone_generated_activities(self, source_package, options, messages, mapping_activity_set):
        """Clones generated activities not belonging to a module"""

        messages.append(("Information", "Cloning Generated Activities not belonging to a Module", ""))
        activities = \
            Activity.objects.all().filter(package=source_package). \
            filter(activity_set__isnull=False).filter(module__isnull=True)
        for activity in activities:
            # Ignore project related activities
            if activity.activity_set.project:
                continue
            # Record details
            messages.append(("Cloned", "Generated Activity", str(activity)))
            # Invalidate the primary key to force save
            activity.pk = None
            # Point the new instance at the current package
            activity.package = self
            # Map the activity set to its clone
            activity.activity_set = ActivitySet.objects.get(pk=mapping_activity_set[activity.activity_set.pk])
            activity.save()

    def __clone_custom_activities(self, source_package, options, messages):
        """Clones activities not belonging to a set or module"""

        messages.append(("Information", "Cloning Custom Activities not belonging to a Module", ""))
        activities = Activity.objects.all().filter(package=source_package).filter(activity_set__isnull=True).filter(
            module__isnull=True)
        for activity in activities:
            # Record details
            messages.append(("Cloned", "Custom Activity", str(activity)))
            # Invalidate the primary key to force save
            activity.pk = None
            # Point the new instance at the current package
            activity.package = self
            activity.save()

    def __clone_module_data(self, source_package, options, messages, mapping_activity_set, programme_mapping):
        """Clones modules, module activities and module staff"""

        messages.append(("Information", "Cloning Module Data", ""))
        # Create a mapping dict
        mapping_module = dict()

        modules = Module.objects.all().filter(package=source_package)
        for module in modules:
            # Grab the activities associates with the module before the key changed, including generated
            # events with an activity set
            activities = Activity.objects.all().filter(package=source_package).filter(module=module)
            # Grab the associated allocations before the key changes
            modulestaff = ModuleStaff.objects.all().filter(module=module)
            # Record the cloned module
            messages.append(("Cloned", "Module", str(module)))
            # Record the original primary key
            original_pk = module.pk
            # Invalidate the primary key to force save    
            module.pk = None
            # Point the new instance at the current package
            module.package = self

            # Correct programme mappings to the new copies, first for the lead_programme, but only if data is there
            if module.lead_programme:
                module.lead_programme = Programme.objects.get(pk=programme_mapping[module.lead_programme.pk])
            # And now for the slightly more complex many to many programmes
            # We need to force a save before Many to Many mappings can be corrected.
            module.save()

            old_module = Module.objects.get(pk=original_pk)
            old_module_programmes = old_module.programmes.all()

            for old_programme in old_module_programmes:
                # Remove the old programme reference
                module.programmes.remove(old_programme)
                # And add the mapped (new) one
                module.programmes.add(Programme.objects.get(pk=programme_mapping[old_programme.pk]))
            # Save the many to manys
            module.save()

            # Make a record of the mapping
            mapping_module.update({original_pk: module.pk})

            # Copy the module activities if needed
            if options['copy_activities_modules']:
                messages.append(("Information", "Cloning Module Activities", ""))
                for activity in activities:
                    # Ignore project related activities
                    if activity.activity_set and activity.activity_set.project:
                        continue
                    # Record the cloned activity
                    messages.append(("Cloned", "Module Activity", str(activity)))
                    # Invalidate the primary key to force save
                    activity.pk = None
                    # Point the new instance at the current package
                    activity.package = self
                    # Point the module at the new instance
                    activity.module = module
                    # Is it part of a mapped activity set?) If so, map this also (generated module activities)
                    if activity.activity_set:
                        activity.activity_set = ActivitySet.objects.get(
                            pk=mapping_activity_set[activity.activity_set.pk])
                    activity.save()

            # And now copy Module Allocations if needed
            if options['copy_modulestaff']:
                messages.append(("Information", "Cloning Module/Staff Allocations", ""))
                for allocation in modulestaff:
                    # Record the cloned allocation
                    messages.append(("Cloned", "Module/Staff Allocation", str(allocation)))
                    # Invalidate the module key
                    allocation.pk = None
                    # Point the new instance at the current package and module
                    allocation.module = module
                    allocation.package = self
                    allocation.save()

        return mapping_module


    def __clone_check_options(self, options, messages):
        """Checks for logically inconsistent options"""

        errors = False

        if options['copy_modules'] and not options['copy_programmes']:
            messages.append(("Error", "Must copy programmes if copying modules", "Aborting"))
            errors = True

        return errors


    def clone_from(self, source_package, options):
        """Copy from another package into the current package

        source_package          the package from which to copy
        options                 a dictionary of options with values as below

            options values

            copy_programmes              copy programmes
            copy_modules                 copy modules
            copy_modulestaff             copy staff allocated to modules
            copy_activities_generated    copy activities from a generator
            copy_activities_custom       copy activities from no module or generator
            copy_activities_module       copy custom activities for a module
            generate_projects            create activities arising from projects

        returns a list of tuples showing what has been cloned
        """

        # Record data on cloned items, errors etc for reporting to the user
        messages = []

        if (Activity.objects.filter(package=self).count()
                + Programme.objects.filter(package=self).count()
                + Module.objects.filter(package=self).count()
                + ModuleStaff.objects.filter(package=self).count()) > 0:
            messages.append(("Error", "Destination Workpackage not empty", "Aborting"))
            return messages

        if options['copy_programmes']:
            programme_mapping = self.__clone_programmes(source_package, options, messages)

        # We need to make to work out what activity sets are in play, make copies and recall a mapping        
        if options['copy_activities_generated']:
            mapping_activity_set = self.__clone_activity_sets(source_package, options, messages)
            self.__clone_generated_activities(source_package, options, messages, mapping_activity_set)

        # Copy Activities that are not associated with a Module or an ActivitySet
        if options['copy_activities_custom']:
            self.__clone_custom_activities(source_package, options, messages)

        # Copy Modules
        if options['copy_modules']:
            self.__clone_module_data(source_package, options, messages, mapping_activity_set, programme_mapping)

        return messages

    def get_all_staff(self):
        """obtains all staff related to by a package"""
        target_groups = self.groups.all()
        # These are user objects
        users_by_groups = User.objects.all().filter(groups__in=target_groups).distinct().order_by('last_name')
        # Get the matching staff objects
        staff = Staff.objects.all().filter(user__in=users_by_groups).distinct().order_by('user__last_name')
        return staff

    def in_the_past(self):
        """Returns whether the workpackage ended before the current date"""
        now = datetime.datetime.today().date()
        return self.enddate < now

    def in_the_future(self):
        """Returns whether the workpackage starts after the current date"""
        now = datetime.datetime.today().date()
        return now < self.startdate

    class Meta:
        ordering = ['name', '-startdate']


class ExternalExaminer(models.Model):
    """Augments the Django user model with external examiner details

    user            the Django user object, a one to one link
    title           the title of the member of staff (Dr, Mr etc)
    staff_number    the staff number (may be an associate code)
    package         the active work package to edit or display
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    staff_number = models.CharField(max_length=20)
    package = models.ForeignKey(WorkPackage, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.title + ' ' + self.user.first_name + ' ' + self.user.last_name

    def is_active(self):
        """Maps to whether the underlying user is active"""
        return self.user.is_active

    def get_examined_programmes(self):
        examined_programmes = Programme.objects.all().filter(examiners=self).distinct()
        return examined_programmes

    def can_access_module(self, module):
        """Checks if the examiner should have general access to a module"""

        examined_programmes = self.get_examined_programmes()

        # External Examiners can download if they examine the lead programme
        if module.lead_programme:
            if module.lead_programme in examined_programmes:
                return True

        # Or if they are an examiner (for information) for another listed programme
        if module.programmes:
            if any(programme in examined_programmes for programme in module.programmes.all()):
                return True

        # Otherwise, there is no access
        return False


class StaffManager(models.Manager):
    """Manager for staff to enforce ordering

    The Staff object is linked to the User object, but there seems no way to enforce
    default ordering by User.last_name short of this."""

    # TODO: This may not be necessary in the future if a custom admin interface is put in place

    def get_queryset(self):
        return super(StaffManager, self).get_queryset().order_by("user__last_name", "user__first_name")


class Staff(models.Model):
    """Augments the Django user model with staff details

    user            the Django user object, a one to one link
    title           the title of the member of staff (Dr, Mr etc)
    staff_number    the staff number
    fte             the percentage of time the member of staff is available for
    package         the active work package to edit or display
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    staff_number = models.CharField(max_length=20)
    fte = models.PositiveSmallIntegerField(default=100)
    package = models.ForeignKey(WorkPackage, null=True, on_delete=models.SET_NULL)

    objects = StaffManager()

    def __str__(self):
        return self.title + ' ' + self.user.first_name + ' ' + self.user.last_name

    def first_name(self):
        """return the first name of the linked user account"""
        return self.user.first_name

    def last_name(self):
        """return the last name of the linked user account"""
        return self.user.last_name

    def hours_by_semester(self, package=0):
        """Calculate the total allocated hours for a given WorkPackage

        If package is zero it attempts to find the value for the logged in user
        """
        semester1_hours = 0.0
        semester2_hours = 0.0
        semester3_hours = 0.0

        # Fetch all the allocated activities for this member of staff
        activities = Activity.objects.all().filter(staff=self.id).filter(package=package)
        for activity in activities:
            hours_by_semester = activity.hours_by_semester()
            semester1_hours += hours_by_semester[1]
            semester2_hours += hours_by_semester[2]
            semester3_hours += hours_by_semester[3]

        # Add hours calculated from "automatic" module allocation
        modulestaff = ModuleStaff.objects.all().filter(staff=self.id).filter(package=package)
        for moduledata in modulestaff:
            c_hours = moduledata.module.get_contact_hours_by_semester()
            as_hours = moduledata.module.get_assessment_hours_by_semester()
            ad_hours = moduledata.module.get_admin_hours_by_semester()

            semester1_hours += int(c_hours[1] * moduledata.contact_proportion / 100)
            semester1_hours += int(as_hours[1] * moduledata.assessment_proportion / 100)
            semester1_hours += int(ad_hours[1] * moduledata.admin_proportion / 100)

            semester2_hours += int(c_hours[2] * moduledata.contact_proportion / 100)
            semester2_hours += int(as_hours[2] * moduledata.assessment_proportion / 100)
            semester2_hours += int(ad_hours[2] * moduledata.admin_proportion / 100)

            semester3_hours += int(c_hours[3] * moduledata.contact_proportion / 100)
            semester3_hours += int(as_hours[3] * moduledata.assessment_proportion / 100)
            semester3_hours += int(ad_hours[3] * moduledata.admin_proportion / 100)

        return [int(semester1_hours + semester2_hours + semester3_hours),
                semester1_hours, semester2_hours, semester3_hours, len(activities)]

    def total_hours(self, package=0):
        """Calculate the total allocated hours"""
        hours_by_semester = self.hours_by_semester(package)
        return hours_by_semester[0]

    def is_active(self):
        """Maps to whether the underlying user is active"""
        return self.user.is_active

    def get_all_tasks(self):
        """Returns a queryset of all unarchived tasks linked to this staff member"""
        user_tasks = Task.objects.all().filter(targets=self).exclude(archive=True).distinct().order_by('deadline')

        # And those assigned against the group
        groups = Group.objects.all().filter(user=self.user)
        group_tasks = Task.objects.all().filter(groups__in=groups).exclude(archive=True).distinct().order_by('deadline')

        # Combine them
        all_tasks = user_tasks | group_tasks

        return all_tasks

    def get_all_packages(self):
        """'Get all the packages that are relevant for a staff member"""
        groups = Group.objects.all().filter(user=self.user)
        packages = WorkPackage.objects.all().filter(groups__in=groups).distinct()

        # Non "staff" users can't see hidden packages.
        if not self.user.is_staff:
            packages = packages.filter(hidden=False)

        return packages

    class Meta:
        verbose_name_plural = 'staff'


class AssessmentStaff(models.Model):
    """Stores which staff can manage Assessment Resources"""

    package = models.ForeignKey(WorkPackage, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    # TODO: what they will have access to.

    class Meta:
        verbose_name_plural = "assessment staff"


# TODO: Sign off of papers


class Category(models.Model):
    """Categories of activity

    name    whether the activity is Teaching, Research etc.
    """

    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "categories"


class ActivityType(models.Model):
    """Defines a type for activities

    name        is the name of the type, e.g. Lectures, Tutorials, Supervision
    category    see the Category model
    """
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Activity(models.Model):
    """Specifies an individual activity that needs allocation

    name             is the name of the activity
    hours            the number of hours allocated is hours_percentage is set to HOURS
    percentage       used to calculate the hours if hours_percentage is set to PERCENTAGE
    hours_percentage one of HOURS or PERCENTAGE as above
    semester         the semester or semesters the activity is in, comma separated
    activity_type    see the related Model
    module           an optional module with which the activity is associated
    comment          any short comment or note
    staff            if not NULL, the staff member allocated this activity
    package          the WorkPackage this activity belongs to
    activity_set     the associated activity_set if this activity is auto generated
    """

    HOURS = 'H'
    PERCENTAGE = 'P'
    HOURPERCENTAGE_CHOICES = (
        (HOURS, 'Hours'),
        (PERCENTAGE, 'Percentage'),
    )
    name = models.CharField(max_length=100)
    hours = models.PositiveSmallIntegerField()
    percentage = models.PositiveSmallIntegerField()
    hours_percentage = models.CharField(max_length=1, choices=HOURPERCENTAGE_CHOICES, default=HOURS)
    semester = models.CharField(max_length=10, validators=[validate_comma_separated_integer_list])
    activity_type = models.ForeignKey('ActivityType', on_delete=models.CASCADE)
    module = models.ForeignKey('Module', blank=True, null=True, on_delete=models.CASCADE)
    comment = models.CharField(max_length=200, default='', blank=True)
    staff = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.SET_NULL)
    package = models.ForeignKey('WorkPackage', on_delete=models.CASCADE)
    activity_set = models.ForeignKey('ActivitySet', blank=True, null=True, on_delete=models.CASCADE)

    def __str__(self):
        if self.module is not None:
            return self.name + ' (' + str(self.module) + ')'
        else:
            return self.name

    def is_allocated(self):
        """returns True if the activity is allocated to a member of staff, False otherwise"""
        return self.staff is not None

    def hours_by_semester(self):
        """Works out the hours in each semester for this activity and returns as a list"""
        # First calculate the hours over all semesters
        if self.hours_percentage == self.HOURS:
            total_hours = self.hours
        else:
            total_hours = self.percentage * self.package.nominal_hours / 100

        return divide_by_semesters(total_hours, self.semester)

    class Meta:
        verbose_name_plural = "activities"


class ActivityGenerator(models.Model):
    """Allows activities common to a number of staff members to be bulk generated and allocated

    Some fields are those from an Activity

    name             is the name of the activity
    hours            the number of hours allocated is hours_percentage is set to HOURS
    percentage       used to calculate the hours if hours_percentage is set to PERCENTAGE
    hours_percentage one of HOURS or PERCENTAGE as above
    semester         the semester or semesters the activity is in, comma separated
    activity_type    see the related Model
    comment          any short comment or note
    package          the WorkPackage this activity belongs to

    details          more detail of the activities
    targets          individual staff for which these activities will be generated
    groups           groups of staff for which these activities will be generated
    """

    HOURS = 'H'
    PERCENTAGE = 'P'
    HOURPERCENTAGE_CHOICES = (
        (HOURS, 'Hours'),
        (PERCENTAGE, 'Percentage'),
    )

    # These fields are essentially those from the Activity model
    name = models.CharField(max_length=300)
    hours = models.PositiveSmallIntegerField()
    percentage = models.PositiveSmallIntegerField()
    hours_percentage = models.CharField(max_length=1, choices=HOURPERCENTAGE_CHOICES, default=HOURS)
    semester = models.CharField(max_length=10, validators=[validate_comma_separated_integer_list])
    activity_type = models.ForeignKey('ActivityType', on_delete=models.CASCADE)
    module = models.ForeignKey('Module', blank=True, null=True, on_delete=models.CASCADE)
    comment = models.CharField(max_length=200, default='', blank=True)
    package = models.ForeignKey(WorkPackage, on_delete=models.CASCADE)

    # These are more associated with the set
    details = models.TextField()
    targets = models.ManyToManyField(Staff, blank=True)
    groups = models.ManyToManyField(Group, blank=True)

    def get_all_targets(self):
        """obtains all targets for a generator whether by user or group, returns a list of valid targets"""
        # These are staff objects
        target_by_users = self.targets.all().order_by('user__last_name')
        target_groups = self.groups.all()
        # These are user objects
        target_by_groups = User.objects.all().filter(groups__in=target_groups).distinct().order_by('last_name')

        # Start to build a queryset, starting with targetted users
        all_targets = target_by_users

        # Add each collection of staff members implicated by group
        for user in target_by_groups:
            staff = Staff.objects.all().filter(user=user)
            all_targets = all_targets | staff

        # Use distinct to clean up any duplicates
        all_targets = all_targets.distinct()

        return all_targets

    def generate_activities(self):
        """Generate all Activities for this"""
        # If there are existing activities, we need to delete them.
        # if(self.activity_set):
        #    self.activity_set.delete()
        #    #TODO: check cascade behaviour!

        # Create a new ActivitySet, point it back at this generator
        activity_set = ActivitySet(name=self.name + " (" + str(self.package) + ")",
                                   generator=self)
        activity_set.save()

        # Now force generation for each allocation against the project
        for staff in self.get_all_targets():
            # Now create the Activity
            activity = Activity(name=self.name,
                                hours=self.hours,
                                percentage=self.percentage,
                                hours_percentage=self.hours_percentage,
                                semester=self.semester,
                                activity_type=self.activity_type,
                                comment=self.comment,
                                staff=staff,
                                module=self.module,
                                package=self.package,
                                activity_set=activity_set
                                )
            activity.save()

    def __str__(self):
        return str(self.name) + " (" + str(self.package) + ")"

    class Meta:
        ordering = ['name']


class Campus(models.Model):
    """This indicated the campus or site that a module is delivered at"""

    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "campuses"
        ordering = ['name']


class ModuleStaff(models.Model):
    """Members of staff given a proportion of module time

    While it is possible to manually allocate all aspects of module work
    as an activity, this allows the normal assumption of a member of
    staff who is responsible for a percentage of different aspects of
    a module
    """

    module = models.ForeignKey('Module', on_delete=models.CASCADE)
    staff = models.ForeignKey('Staff', on_delete=models.CASCADE)
    package = models.ForeignKey('WorkPackage', on_delete=models.CASCADE)
    # TODO package is implicitly linked by module already...?

    contact_proportion = models.PositiveSmallIntegerField()
    admin_proportion = models.PositiveSmallIntegerField()
    assessment_proportion = models.PositiveSmallIntegerField()

    def __str__(self):
        return str(self.module) + " : " + str(self.staff)

    class Meta:
        verbose_name_plural = "module staff"


class ModuleSize(models.Model):
    """Basic notion of module size in intervals

    text                describing the module size, as, for instance 0-10
    admin_scaling       multiplier on the normal assumption of admin hours
    assessment_scaling  multiplied on the normal assumption of assessment hours
    """

    text = models.CharField(max_length=10)
    admin_scaling = models.FloatField()
    assessment_scaling = models.FloatField()

    def __str__(self):
        return str(self.text)


class Programme(models.Model):
    """Basic information about a programme of study

    programme_code  the code for the programme (e.g. 7644)
    programme_name  the name of the programme
    examiners       all the external examiners associated with the programme
    package         the package this programme is associated with
    directors
    """

    programme_code = models.CharField(max_length=10)
    programme_name = models.CharField(max_length=200)
    examiners = models.ManyToManyField(ExternalExaminer, blank=True)
    package = models.ForeignKey('WorkPackage', on_delete=models.CASCADE)
    directors = models.ManyToManyField(Staff, blank=True)

    def __str__(self):
        return str(self.programme_code) + ': ' + str(self.programme_name)

    class Meta:
        ordering = ['programme_name']


class Module(models.Model):
    """Basic information about a module

    module_code     the code for the module (e.g. EEE122)
    module_name     the module name
    semester        a Comma Separated Variable list of semesters the module covers
    size            the approximate size of the module
    contact_hours   the main contact hours for the module
    admin_hours     admin hours, blank for automatic calculation
    assessment_hours    assessment, hours, blank for automatic calculation
    package         the package this module (instance) is associated with
    programmes      the programmes the module belongs to
    lead_programme  a main programme for the purposes of external examination
    coordinator     the staff member primarily responsible for the module
    moderators      any staff members who can moderate this module's assessments

    Eventually augmenting this from CMS would be useful
    """

    module_code = models.CharField(max_length=10)
    module_name = models.CharField(max_length=200)
    campus = models.ForeignKey('Campus', on_delete=models.CASCADE)
    semester = models.CharField(max_length=10, validators=[validate_comma_separated_integer_list])
    credits = models.PositiveSmallIntegerField(default=20)
    size = models.ForeignKey('ModuleSize', on_delete=models.CASCADE)
    contact_hours = models.PositiveSmallIntegerField(blank=True, null=True)
    admin_hours = models.PositiveSmallIntegerField(blank=True, null=True)
    assessment_hours = models.PositiveSmallIntegerField(blank=True, null=True)
    package = models.ForeignKey('WorkPackage', on_delete=models.CASCADE)
    details = models.TextField(blank=True, null=True)
    programmes = models.ManyToManyField(Programme, blank=True, related_name='modules')
    lead_programme = models.ForeignKey(Programme, blank=True, null=True, related_name='lead_modules', on_delete=models.SET_NULL)
    coordinator = models.ForeignKey(Staff, blank=True, null=True, related_name='coordinated_modules', on_delete=models.SET_NULL)
    moderators = models.ManyToManyField(Staff, blank=True, related_name='moderated_modules')

    def get_contact_hours(self):
        """returns the contact hours for the module

        If the override is set, this is returns, otherwise an assumption is made
        """
        if self.contact_hours is None:
            hours = self.credits * self.package.credit_contact_scaling
        else:
            hours = self.contact_hours

        return hours

    def get_contact_hours_by_semester(self):
        """returns the list divided by semester of contact hours"""
        return divide_by_semesters(self.get_contact_hours(), self.semester)

    def get_admin_hours(self):
        """returns the total admin hours"""
        if self.admin_hours is None:
            hours = self.get_contact_hours() * self.package.contact_admin_scaling * self.size.admin_scaling
        else:
            hours = self.admin_hours
        return hours

    def get_admin_hours_by_semester(self):
        """returns the list divided by semester of admin hours"""
        return divide_by_semesters(self.get_admin_hours(), self.semester)

    def get_assessment_hours(self):
        """returns the total assessment hours"""
        if self.assessment_hours is None:
            hours = self.get_contact_hours() * self.package.contact_assessment_scaling * self.size.assessment_scaling
        else:
            hours = self.assessment_hours
        return hours

    def get_assessment_hours_by_semester(self):
        """returns the list divided by semester of assessment hours"""
        return divide_by_semesters(self.get_assessment_hours(), self.semester)

    def get_all_hours(self):
        """returns the total hours for the module"""
        c_hours = self.get_contact_hours()
        ad_hours = self.get_admin_hours()
        as_hours = self.get_assessment_hours()

        return c_hours + ad_hours + as_hours

    def get_all_hours_by_semester(self):
        """returns the list divided by semester of the total hours for the module"""
        return divide_by_semesters(self.get_all_hours(), self.semester)

    def get_assessment_history(self):
        """returns a list of tuples of AssessmentState objects and the resources signed off"""

        # Get the signoffs and resources in chronological order
        signoffs = AssessmentStateSignOff.objects.all().filter(module=self).order_by('created')
        resources = AssessmentResource.objects.all().filter(module=self).order_by('created')

        # Make a list of tuples
        history = list()

        for counter, signoff in enumerate(signoffs):
            # Get the resources covered by this sign off, in reverse chronological order
            slice = resources.filter(created__lt=signoff.created).order_by('-created')
            # Exclude them from the next iteration
            resources = resources.exclude(created__lt=signoff.created)
            # Add the tuple of the sign off and slice of resources to the list
            history.append((signoff, slice))

        # If any remaining resources aren't signed off, add them against a None object
        if len(resources):
            history.append((None, resources.order_by('-created')))

        # So the list is chronological, and we'll want most recent first, so
        history.reverse()

        return history

    def __str__(self):
        return self.module_code + ' : ' + self.module_name

    class Meta:
        ordering = ['module_code']


class Task(models.Model):
    """A task that members of staff will be allocated

    These are usually much smaller than Activities and are deadline driven

    name        a name for the task
    url         an optional URL giving more information
    category    see the Category model
    details     a potentially large area of text giving more information
    deadline    the time by which the task should be completed
    archive     whether the task is completed / archived
    targets     those staff the task is allocated to

    See also the TaskCompletion model. Note that targets should not be removed
    on completion.
    """

    name = models.CharField(max_length=100)
    url = models.URLField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    details = models.TextField()
    deadline = models.DateTimeField()
    archive = models.BooleanField(default=False)
    targets = models.ManyToManyField(Staff, blank=True)
    groups = models.ManyToManyField(Group, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name + ' due ' + str(self.deadline)

    def get_all_targets(self):
        """obtains all targets for a task whether by user or group, returns a list of valid targets"""
        # These are staff objects
        target_by_users = self.targets.all().order_by('user__last_name')
        target_groups = self.groups.all()
        # These are user objects
        target_by_groups = User.objects.all().filter(groups__in=target_groups).distinct().order_by('last_name')

        # Start to build a queryset, starting with targetted users
        all_targets = target_by_users

        # Add each collection of staff members implicated by group
        for user in target_by_groups:
            staff = Staff.objects.all().filter(user=user)
            all_targets = all_targets | staff

        # Use distinct to clean up any duplicates
        all_targets = all_targets.distinct()

        return all_targets

    def is_urgent(self):
        """returns True is the task is 7 days away or less, False otherwise"""
        now = datetime.datetime.utcnow().replace(tzinfo=utc)
        seconds_left = (self.deadline - now).total_seconds()
        # If a task is less than a week from deadline consider it urgent
        return bool(seconds_left < 60 * 60 * 24 * 7)

    def is_overdue(self):
        """returns True is the deadline has passed, False otherwise"""
        now = datetime.datetime.utcnow().replace(tzinfo=utc)
        seconds_left = (self.deadline - now).total_seconds()
        return bool(seconds_left < 0)


class TaskCompletion(models.Model):
    """This indicates that a staff member has completed a given task

    task    See the Task model
    Staff   See the Staff model
    when    a datetime stamp of when the task was completed
    comment an optional comment on completion

    """
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    comment = models.CharField(max_length=200, default='', blank=True)
    when = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.task.name + ' completed by ' + str(self.staff) + ' on ' + str(self.when)


class Resource(models.Model):
    """A file resource to be made available for staff

    name        A descriptive name for the resource
    file        The file information
    category    See the Category model
    created     When the resource was added
    modified    When the resource was modified
    downloads   A download counter
    """

    name = models.CharField(max_length=200)
    file = models.FileField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    downloads = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return self.name


class AssessmentResourceType(models.Model):
    """Type of assessment file (e.g. exam, solution etc)"""

    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class AssessmentResource(models.Model):
    """A file resource to be made available for staff

    name        A descriptive name for the resource
    details     Optional extended details
    resource    The file information
    module      The module associated
    category    See the Category model
    created     When the resource was added
    modified    When the resource was modified
    downloads   A download counter
    owner       The uploader
    """

    name = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    resource = models.FileField(upload_to='assessments/%Y/%m/%d/')
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    resource_type = models.ForeignKey(AssessmentResourceType, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    downloads = models.PositiveSmallIntegerField(default=0)
    owner = models.ForeignKey(Staff, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    def is_downloadable_by_staff(self, staff):
        """determines if a specific Staff member may download the resource

            Staff can download a resource if and only if:

            They coordinate the linked module;
            They are specifically designated in AssessmentStaff for the resource package; or
            They are the content owner (uploader); or
            They are in the teaching team for the associated module in that package; or
            They are a designated moderator for the associated module in that package.

            returns True if permitted, False otherwise
        """

        # Ensure we have a Staff object
        if not isinstance(staff, Staff):
            return False

        # Module Coordinators can download
        if self.module.coordinator == staff:
            return True

        # Specifically designated assessment staff can download
        if len(AssessmentStaff.objects.all().filter(staff=staff).filter(package=self.module.package)):
            return True

        # The owner can download
        if staff == self.owner:
            return True

        # People on the teaching team can download
        if len(ModuleStaff.objects.all().filter(module=self.module).filter(staff=staff)):
            return True

        # A moderator can download
        for moderator in self.module.moderators.all():
            if staff == moderator:
                return True

        # Otherwise, there is no access
        return False

    def is_downloadable_by_external(self, external):
        """determines if a specific ExternalExaminer member may download the resource

            The examiner can download a resource if and only if:

            They are the lead examiner for the module the resource belongs to in that package;
            They are an examiner for a programme that the resource module belongs to in that package;

            returns True if permitted, False otherwise
        """

        # Ensure we have an Examiner object
        if not isinstance(external, ExternalExaminer):
            return False

        return external.can_access_module(self.module)

    def is_downloadable_by(self, person):
        """checks is a resource is downloadable by a member of Staff or an ExternalExaminer

            see is_downloadable_by_staff() or is_downloadable_by_external() for more details

            returns True if permitted, False otherwise
        """
        if isinstance(person, Staff):
            return self.is_downloadable_by_staff(person)

        if isinstance(person, ExternalExaminer):
            return self.is_downloadable_by_external(person)

        return False


class AssessmentState(models.Model):
    """Allows for configurable Assessment Resource Workflow

    name            The name of the state
    description     More details on the state
    actors          The user types who can create this state, CSV field
    notify          The user types to notify that the state has been created
    initial_state   Can this be an initial state?
    next_states     Permissible states to move to from this one
    priority        To allow the states to be sorted for presentation to the user

    actors and notify should be comma separated lists as in USER_TYPES below.
    """

    ANYONE = 'anyone'
    COORDINATOR = 'coordinator'
    MODERATOR = 'moderator'
    EXTERNAL = 'external'
    TEAM_MEMBER = 'team_member'
    ASSESSMENT_STAFF = 'assessment_staff'

    USER_TYPES = (
        (ANYONE, 'Any logged in user'),
        (COORDINATOR, 'Module coordinator'),
        (MODERATOR, 'Module moderator'),
        (TEAM_MEMBER, 'Module teaching team member'),
        (EXTERNAL, 'External Examiner'),
        (ASSESSMENT_STAFF, 'Members of AssessmentStaff'),
        ('exams_office', 'Exams Office')
    )

    name = models.CharField(max_length=200)
    description = models.TextField()
    actors = models.TextField()
    notify = models.TextField()
    initial_state = models.BooleanField(default = False)
    next_states = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='children')
    priority = models.IntegerField()

    def __str__(self):
        return str (self.name)

    def get_actor_list(self):
        """Return a list of acceptable actors"""
        return self.actors.split(',')

    def get_notify_list(self):
        """Return a list of acceptable actors"""
        return self.notify.split(',')

    def can_be_set_by(self, person, module):
        """checks if a State can be set on a given module by a giver person

            see is_downloadable_by_staff() or is_downloadable_by_external() for more details

            returns True if permitted, False otherwise
        """
        if isinstance(person, Staff):
            return self.can_be_set_by_staff(person, module)

        if isinstance(person, ExternalExaminer):
            return self.can_be_set_by_external(person, module)

        return False

    def can_be_set_by_staff(self, staff, module):
        """determines if a member of staff can set this state for a module

            returns True if permitted, False otherwise"""

        actors = self.get_actor_list()

        # SuperUser override
        if staff.user.is_superuser:
            return True

        # Anyone
        if self.ANYONE in actors:
            return True

        # Module Coordinator?
        if self.COORDINATOR in actors and staff == module.coordinator:
            return True

        # Moderator
        if self.MODERATOR in actors and staff in module.moderators.all():
            return True

        # Team member
        if self.TEAM_MEMBER in actors and len(ModuleStaff.objects.all().filter(module=module).filter(staff=staff)):
            return True

        # Assessment Staff
        if self.ASSESSMENT_STAFF in actors and \
            len(AssessmentStaff.objects.all().filter(staff=staff).filter(package=module.package)):
            return True

        return False

    def can_be_set_by_external(self, external, module):
        """determines if a specific ExternalExaminer member may set this state for a module

            returns True if permitted, False otherwise
        """

        # Ensure we have an Examiner object
        if not isinstance(external, ExternalExaminer):
            return False

        # If external is not in the actor list, reject
        if not self.EXTERNAL in self.get_actor_list():
            return False

        # Now it's about checking they have permission at all
        return external.can_access_module(module)

    class Meta:
        ordering = ['priority']



class AssessmentStateSignOff(models.Model):
    """Marks a particular sign off of an AssessmentState for a module

    module              The module being signed off
    assessment_state    The AssessmentState being used
    signed_by           The user signing off (Could be Staff or Examiner)
    created             The datestamp for signoff
    notified            The datestamp for notificiations sent
    notes               Any comments
    """

    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    assessment_state = models.ForeignKey(AssessmentState, on_delete=models.CASCADE)
    signed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    notified = models.DateTimeField(null=True, blank=True)
    notes = models.TextField()

    def __str__(self):
        return str (self.assessment_state)


class LoadTracking(models.Model):
    """Tracks what the total School loads are at any given time"""

    academic_year = models.CharField(max_length=10, default=ACADEMIC_YEAR)

    semester1_hours = models.DecimalField(decimal_places=2, max_digits=15)
    semester2_hours = models.DecimalField(decimal_places=2, max_digits=15)
    semester3_hours = models.DecimalField(decimal_places=2, max_digits=15)

    total_hours = models.DecimalField(decimal_places=2, max_digits=15)
    mean = models.DecimalField(decimal_places=2, max_digits=15)
    sd = models.DecimalField(decimal_places=2, max_digits=15)

    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.total_hours)


class CourseworkTracker(models.Model):
    """Tracks Coursework progress through the QA System

    academic_year   The academic year in 2014/2015 format
    module          See the Module model
    progress        A string showing the progress
    created         A timestamp for this event
    """

    # TODO Let's see if we can track user with this at some point
    # http://stackoverflow.com/questions/4670783/make-the-user-in-a-model-default-to-the-current-user
    SET = 'SET'
    MODERATE = 'MODERATE'
    EXTERNAL = 'EXTERNAL'
    REWORK = 'REWORK'
    EXAMOFFICE = 'EXAMOFFICE'
    PROGRESS_CHOICES = (
        (SET, 'Coursework Set'),
        (MODERATE, 'Internal Moderation'),
        (EXTERNAL, 'Sent to External Examiner'),
        (REWORK, 'Reworked'),
        (EXAMOFFICE, 'Submitted to Exams Office'),
    )

    academic_year = models.CharField(max_length=10, default=ACADEMIC_YEAR)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    progress = models.CharField(max_length=15, choices=PROGRESS_CHOICES, default=SET)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.module) + ' ' + str(self.academic_year) + ' ' + str(self.progress) + ' ' + str(self.created)


class ExamTracker(models.Model):
    """Tracks Exam progress through the QA System

    academic_year   The academic year in 2014/2015 format
    module          See the Module model
    progress        A string showing the progress
    created         A timestamp for this event
    """

    SET = 'SET'
    MODERATE = 'MODERATE'
    EXTERNAL = 'EXTERNAL'
    REWORK = 'REWORK'
    EXAMOFFICE = 'EXAMOFFICE'
    PROGRESS_CHOICES = (
        (SET, 'Exam Set'),
        (MODERATE, 'Internal Moderation'),
        (EXTERNAL, 'Sent to External Examiner'),
        (REWORK, 'Reworked'),
        (EXAMOFFICE, 'Submitted to Exams Office'),
    )

    academic_year = models.CharField(max_length=10, default=ACADEMIC_YEAR)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    progress = models.CharField(max_length=15, choices=PROGRESS_CHOICES, default=SET)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.module) + ' ' + str(self.academic_year) + ' ' + str(self.progress) + ' ' + str(self.created)


class Body(models.Model):
    """Information on Project and Grant Providers

    name    name of the grant providing body
    details any more details for that body"""

    name = models.CharField(max_length=300)
    details = models.TextField()

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name_plural = "bodies"
        ordering = ['name']


class Project(models.Model):
    """Significant, often multi staff projects. Research grants would be a common example
    Information to do with Project duration, start, end etc.

    name            the name of the grant
    start           the date the grant starts
    end             the date the grant ends
    activity_type   the activity type which also maps to category of the project (T&L / R&D etc.)
    activity_set    if there are generated activities, they are in this set
    body            an associated body (could be a funding body)"""

    name = models.CharField(max_length=300)
    start = models.DateField()
    end = models.DateField()
    body = models.ForeignKey(Body, on_delete=models.CASCADE)
    activity_type = models.ForeignKey(ActivityType, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.name) + ' (' + str(self.body) + ')'

    def generate_activities(self):
        """Generate all the Activity records associated with the project"""

        # If there are existing activities, we need to delete them. Find linked sets.
        # Cascade will kill linked activities
        ActivitySet.objects.all().filter(project=self).delete()

        # Create a new ActivitySet
        activity_set = ActivitySet(name=self.name, project=self)
        activity_set.save()

        # Now force generation for each allocation against the project
        project_staff = ProjectStaff.objects.all().filter(project=self)
        for allocation in project_staff:
            allocation.generate_activities(activity_set)

    class Meta:
        ordering = ['name', '-start']


class ProjectStaff(models.Model):
    """Staff commitment to a Project/Grant
    
    There may be several instances of these objects for members of staff for whom the
    workload increases or decreases over the period of the grant.

    staff           The academic member of staff
    project         The project worked upon
    start           The start of this work (should be >= start in associated Grant)
    end             The end of this work (should be <= end in associated Grant)
    hours_per_week  The hours per week (excluding holidays) in this period
    """

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    start = models.DateField()
    end = models.DateField()
    hours_per_week = models.FloatField()

    def __str__(self):
        return str(self.staff) + ' (' + str(self.project) + ')'

    def generate_activities(self, activity_set):
        """Create activities associated with this allocation"""
        # TODO: Currently creates activities equally mapped on semesters, could be refined
        # TODO: If workpackages overlap in timing or staff, hours may be double counted
        # TODO: If there is project time outside any workpackage it will be "lost"
        # TODO: Also there is no protection for overlapping allocations for the same staff member

        work_done = []
        # Get all the work packages for the staff member and go through each
        packages = self.staff.get_all_packages()
        for package in packages:
            # Work out the overlap of the project with this package
            start_overlap = max(package.startdate, self.start)
            end_overlap = min(package.enddate, self.end)

            in_package_days = (end_overlap - start_overlap).days
            if in_package_days <= 0:
                # No days in this package, move along...
                continue

            all_package_days = (package.enddate - package.startdate).days
            # Get total working days taking into account leave and weekends
            working_days = package.working_days * in_package_days / all_package_days
            # Get weeks by dividing by number of working days in a week (usually 5)
            working_weeks = working_days / package.days_in_week
            hours = working_weeks * self.hours_per_week

            # Now create the Activity
            activity = Activity(name=str(self.project),
                                hours=hours,
                                percentage=0,
                                hours_percentage=Activity.HOURS,
                                semester='1,2,3',
                                activity_type=self.project.activity_type,
                                comment='Auto Generated from Project',
                                staff=self.staff,
                                package=package,
                                activity_set=activity_set
                                )
            activity.save()

    class Meta:
        verbose_name_plural = "project staff"
        ordering = ['staff', '-start']


class ActivitySet(models.Model):
    """Groups a set of automatically generated activities, to be deleted or regenerated in future.
    This may reflect materials produced by ActivityGenerator objects, or Grant objects and thus may
    span groups of Staff and/or WorkPackages. This is used to abstract that connection.
    
    name        taken from the appropriate generator
    created     an automatically generated timestamp when the set was created
    project     if the set is associated with a project, this is that key
    generator   if the set is associated with a generator, this is that key"""

    name = models.CharField(max_length=300)
    created = models.DateTimeField(auto_now_add=True)
    project = models.ForeignKey(Project, blank=True, null=True, on_delete=models.CASCADE)
    generator = models.ForeignKey(ActivityGenerator, blank=True, null=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name
