from django.db import models
from django.contrib.auth.models import User, Group

# code to handle timezones
from django.utils.timezone import utc
import datetime

#from . import helper_functions

#TODO: Needs more elegant handling than this
ACADEMIC_YEAR='2015/2016'
NOMINAL_HOURS=1600

CREDIT_TO_CONTACT_SCALING = 8/20
CONTACT_TO_ADMIN_SCALING = 1
CONTACT_TO_ASSESSMENT_SCALING = 1

def divide_by_semesters(total_hours, semester_string):
    """divide hours equally between targeted semesters
    
    total_hours     the total number of hours to divide
    semester_string comma separated list of semesters
    
    returns a list with hours in each of three semesters
    followed by the total itself
    """
    semesters = semester_string.split(',')
    
    # Create a list to contain their subdivision
    split_hours = list()
    # How many semesters are listed?
    no_semesters = len(semesters)
    # We currently have three semesters, 1, 2 and 3
    for s in range(1,4):
        # Check if this one is flagged, brutally ugly code :-(
        # TODO: Try and fix the abomination 
        if semester_string.count(str(s)) > 0:
            split_hours.append(total_hours / no_semesters)
        else:
            # Nothing in this semester
            split_hours.append(0)
    
    split_hours.append(total_hours)        
    return split_hours
    

class Staff(models.Model):
    '''Augments the Django user model with staff details
    
    user            the Django user object, a one to one link
    title           the title of the member of staff (Dr, Mr etc)
    staff_number    the staff number
    fte             the percentage of time the member of staff is available for
    '''
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    staff_number = models.CharField(max_length=20)
    fte = models.PositiveSmallIntegerField(default=100)
    
    def __str__(self):
        return self.title + ' ' + self.user.first_name + ' ' + self.user.last_name
        
    def first_name(self):
        return self.user.first_name
        
    def last_name(self):
        return self.user.last_name
        
    def hours_by_semester(self, academic_year = ACADEMIC_YEAR):
        '''Calculate the total allocated hours'''
        semester1_hours = 0
        semester2_hours = 0
        semester3_hours = 0
        
        # Fetch all the allocated activities for this member of staff
        activities = Activity.objects.all().filter(staff=self.id).filter(academic_year=academic_year)
        for activity in activities:
            hours_by_semester = activity.hours_by_semester()
            semester1_hours += hours_by_semester[0]
            semester2_hours += hours_by_semester[1]
            semester3_hours += hours_by_semester[2]
            
        # Add hours calculated from "automatic" module allocation
        modulestaff = ModuleStaff.objects.all().filter(staff=self.id).filter(academic_year=academic_year)
        for moduledata in modulestaff:
            c_hours = moduledata.module.get_contact_hours_by_semester()
            as_hours = moduledata.module.get_assessment_hours_by_semester()
            ad_hours = moduledata.module.get_admin_hours_by_semester()

            semester1_hours += c_hours[0] * moduledata.contact_proportion / 100
            semester1_hours += as_hours[0] * moduledata.assessment_proportion / 100
            semester1_hours += ad_hours[0] * moduledata.admin_proportion / 100

            semester2_hours += c_hours[1] * moduledata.contact_proportion / 100
            semester2_hours += as_hours[1] * moduledata.assessment_proportion / 100
            semester2_hours += ad_hours[1] * moduledata.admin_proportion / 100

            semester3_hours += c_hours[2] * moduledata.contact_proportion / 100
            semester3_hours += as_hours[2] * moduledata.assessment_proportion / 100
            semester3_hours += ad_hours[2] * moduledata.admin_proportion / 100            
            
            
        return [semester1_hours, semester2_hours, semester3_hours,
            int(semester1_hours + semester2_hours + semester3_hours), len(activities)]
    
    def total_hours(self, academic_year = ACADEMIC_YEAR):
        '''Calculate the total allocated hours'''
        hours_by_semester = self.hours_by_semester(academic_year)
        return hours_by_semester[3]
        
    def get_all_tasks(self):
        '''Returns a queryset of all unarchived tasks linked to this staff member'''
        user_tasks = Task.objects.all().filter(targets=self).exclude(archive=True).distinct().order_by('deadline')
    
        # And those assigned against the group
        groups = Group.objects.all().filter(user=self.user)
        group_tasks = Task.objects.all().filter(groups__in=groups).distinct().order_by('deadline')
    
        # Combine them
        all_tasks = user_tasks | group_tasks
        
        return all_tasks
    
            
    class Meta:
        verbose_name_plural = 'staff'
        order_with_respect_to = 'user'


class Category(models.Model):
    '''Categories of activity
    
    name    whether the activity is Teaching, Research etc.
    '''
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "categories"

    
class ActivityType(models.Model):
    '''Defines a type for activities
    
    name        is the name of the type, e.g. Lectures, Tutorials, Supervision
    category    see the Category model
    '''
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category)
    
    def __str__(self):
        return self.name
    

class Activity(models.Model):
    '''Specifies an individual activity that needs allocation
    
    name             is the name of the activity
    hours            the number of hours allocated is hours_percentage is set to HOURS
    percentage       used to calculate the hours if hours_percentage is set to PERCENTAGE
    hours_percentage one of HOURS or PERCENTAGE as above
    semester         the semester or semesters the activity is in, comma separated
    activity_type    see the related Model
    comment          any short comment or note
    academic_year    the academic year in the form 2015/2016 etc.
    staff            if not NULL, the staff member allocated this activity
    
    '''
    
    HOURS = 'H'
    PERCENTAGE = 'P'
    HOURPERCENTAGE_CHOICES = (
        (HOURS, 'Hours'),
        (PERCENTAGE, 'Percentage'),
    )
    name = models.CharField(max_length = 100)
    hours = models.PositiveSmallIntegerField()
    percentage = models.PositiveSmallIntegerField()
    hours_percentage = models.CharField(max_length = 1, choices = HOURPERCENTAGE_CHOICES, default = HOURS)
    semester = models.CommaSeparatedIntegerField(max_length = 10)
    activity_type = models.ForeignKey('ActivityType')
    module = models.ForeignKey('Module', blank = True, null = True)
    comment = models.CharField(max_length = 200, default='', blank = True)
    academic_year = models.CharField(max_length = 10, default = ACADEMIC_YEAR)
    staff = models.ForeignKey(Staff, null = True, blank = True)
    
    def __str__(self):
        return self.name + ' (' + str(self.module) + ')'
        
    def module_details(self):
        return str(self.module_id)
        
    def is_allocated(self):
        return self.staff is not None
        
    def hours_by_semester(self):
        '''Works out the hours in each semester for this activity and returns as a list'''
        # First calculate the hours over all semesters
        if self.hours_percentage == self.HOURS:
            total_hours = self.hours
        else:
            total_hours = self.percentage * NOMINAL_HOURS / 100
        
        return divide_by_semesters(total_hours, self.semester)        
            
    class Meta:
        verbose_name_plural = "activities"


class Campus(models.Model):
    '''This indicated the campus or site that a module is delivered at'''
    
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name
        
    class Meta:
        verbose_name_plural = "campuses"


class ModuleStaff(models.Model):
    '''Members of staff given a proportion of module time
    
    While it is possible to manually allocate all aspects of module work
    as an activity, this allows the normal assumption of a member of
    staff who is resonsible for a percentage of different aspects of
    a module
    '''
    
    module = models.ForeignKey('Module')
    staff = models.ForeignKey('Staff')
    academic_year = models.CharField(max_length=10, default=ACADEMIC_YEAR)
    
    contact_proportion = models.PositiveSmallIntegerField()
    admin_proportion = models.PositiveSmallIntegerField()
    assessment_proportion = models.PositiveSmallIntegerField()
    
    def __str__(self):
        return str(self.module) + " : " + str(self.staff)
        
    class Meta:
        verbose_name_plural = "module staff"


class ModuleSize(models.Model):
    '''Basic notion of module size in intervals
    
    text                describing the module size, as, for instance 0-10
    admin_scaling       multiplier on the normal assumption of admin hours
    assessment_scaling  multiplied on the normal assumption of assessment hours
    '''
    
    text = models.CharField(max_length=10)
    admin_scaling = models.DecimalField(max_digits=6, decimal_places=2)
    assessment_scaling = models.DecimalField(max_digits=6, decimal_places=2)
    
    def __str__(self):
        return str(self.text)
    
    
class Module(models.Model):
    '''Basic information about a module
    
    module_code     the code for the module (e.g. EEE122)
    module_name     the module name
    semester        a Comma Separated Variable list of semesters the module covers
    size            the approximate size of the module
    contact_hours   the main contact hours for the module
    admin_hours     admin hours, blank for automatic calculation
    assessment_hours    assessment, hours, blank for automatic calculation
    
    Eventually augmenting this from CMS would be useful
    '''
    
    module_code = models.CharField(max_length=10)
    module_name = models.CharField(max_length=200)
    campus = models.ForeignKey('Campus')
    semester = models.CommaSeparatedIntegerField(max_length=10)
    credits = models.PositiveSmallIntegerField(default=20)
    size = models.ForeignKey('ModuleSize')
    contact_hours = models.PositiveSmallIntegerField(blank = True)
    admin_hours = models.PositiveSmallIntegerField(blank = True)
    assessment_hours = models.PositiveSmallIntegerField(blank = True)
    
    def get_contact_hours(self):
        """returns the contact hours for the module
        
        If the override is set, this is returns, otherwise an assumption is made
        """
        if self.contact_hours:
            hours = self.contact_hours
        else:
            hours = self.credits * CREDIT_TO_CONTACT_SCALING
        return hours
        
    def get_contact_hours_by_semester(self):
        return divide_by_semesters(self.get_contact_hours(), self.semester)
    
    def get_admin_hours(self):
        """docstring for get_admin_hours"""
        if self.admin_hours:
            hours = self.admin_hours
        else:
            hours = self.get_contact_hours() * CONTACT_TO_ADMIN_SCALING * float(self.size.admin_scaling)
        return hours
        
    def get_admin_hours_by_semester(self):
        return divide_by_semesters(self.get_admin_hours(), self.semester)
            
    def get_assessment_hours(self):
        """docstring for get_assessment_hours"""
        if self.assessment_hours:
            hours = self.assessment_hours
        else:
            hours = self.get_contact_hours() * CONTACT_TO_ASSESSMENT_SCALING * float(self.size.assessment_scaling)
        return hours
        
    def get_assessment_hours_by_semester(self):
        return divide_by_semesters(self.get_assessment_hours(), self.semester)
        
    def get_all_hours(self):
        c_hours = self.get_contact_hours()
        ad_hours = self.get_admin_hours()
        as_hours = self.get_assessment_hours()
        
        hours = map(operator.add, c_hours, ad_hours, as_hours)
        
        return(hours)
        
    def get_all_hours_by_semester(self):
        return divide_by_demesters(self.get_all_hours())
    
    def __str__(self):
        return self.module_code + ' : ' + self.module_name
    

class Task(models.Model):
    '''A task that members of staff will be allocated
    
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
    '''
    
    name = models.CharField(max_length = 100)
    url = models.URLField(blank = True)
    category = models.ForeignKey(Category)
    details = models.TextField()
    deadline = models.DateTimeField()
    archive = models.BooleanField(default=False)
    targets = models.ManyToManyField(Staff, blank=True)
    groups = models.ManyToManyField(Group, blank=True)
    created = models.DateTimeField(auto_now_add = True)
    modified = models.DateTimeField(auto_now = True)
    
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
        if(seconds_left < 60*60*24*7):
            return True
        else:
            return False
            
    def is_overdue(self):
        """returns True is the deadline has passed, False otherwise"""
        now = datetime.datetime.utcnow().replace(tzinfo=utc)
        seconds_left = (self.deadline - now).total_seconds()
        if(seconds_left < 0):
            return True
        else:
            return False
    
    
class TaskCompletion(models.Model):
    '''This indicates that a staff member has completed a given task
    
    task    See the Task model
    Staff   See the Staff model
    when    a datetime stamp of when the task was completed
    comment an optional comment on completion
    
    '''
    task = models.ForeignKey(Task)
    staff = models.ForeignKey(Staff)
    comment = models.CharField(max_length=200, default='', blank=True)
    when = models.DateTimeField(auto_now_add = True)
    
    def __str__(self):
        return self.task.name + ' completed by ' + str(self.staff) + ' on ' + str(self.when)



    
class Resource(models.Model):
    '''A file resource to be made available for staff
    
    name        A descriptive name for the resource
    file        The file information
    category    See the Category model
    created     When the resource was added
    modified    When the resource was modified
    downloads   A download counter
    '''
    
    name = models.CharField(max_length=200)
    file = models.FileField()
    category = models.ForeignKey(Category)
    created = models.DateTimeField(auto_now_add = True)
    modified = models.DateTimeField(auto_now = True)
    downloads = models.PositiveSmallIntegerField(default = 0)
    
    
    def __str__(self):
        return self.name
    
    
class LoadTracking(models.Model):
    '''Tracks what the total School loads are at any given time'''
    
    academic_year = models.CharField(max_length=10, default=ACADEMIC_YEAR)
    
    semester1_hours = models.DecimalField(decimal_places=2, max_digits=15)
    semester2_hours = models.DecimalField(decimal_places=2, max_digits=15)
    semester3_hours = models.DecimalField(decimal_places=2, max_digits=15)
    
    total_hours = models.DecimalField(decimal_places=2, max_digits=15)
    mean = models.DecimalField(decimal_places=2, max_digits=15)
    sd = models.DecimalField(decimal_places=2, max_digits=15)
    
    created = models.DateTimeField(auto_now_add = True)    
    
    def __str__(self):
        return str(total_hours)
        
        
class CourseworkTracker(models.Model):
    '''Tracks Coursework progress through the QA System
    
    academic_year   The academic year in 2014/2015 format
    module          See the Module model
    progress        A string showing the progress
    created         A timestamp for this event
    '''
    
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
    module = models.ForeignKey(Module)
    progress = models.CharField(max_length = 15, choices = PROGRESS_CHOICES, default = SET)
    created = models.DateTimeField(auto_now_add = True)
    
    def __str__(self):
        return str(self.module) + ' ' + str(self.academic_year) + ' ' + str(self.progress) + ' ' + str(self.created)    


class ExamTracker(models.Model):
    '''Tracks Exam progress through the QA System
    
    academic_year   The academic year in 2014/2015 format
    module          See the Module model
    progress        A string showing the progress
    created         A timestamp for this event
    '''
    
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
    module = models.ForeignKey(Module)
    progress = models.CharField(max_length = 15, choices = PROGRESS_CHOICES, default = SET)
    created = models.DateTimeField(auto_now_add = True)    
    
    def __str__(self):
        return str(self.module) + ' ' + str(self.academic_year) + ' ' + str(self.progress) + ' ' + str(self.created)    
