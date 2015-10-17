from django.db import models
from django.contrib.auth.models import User, Group

#TODO: Needs more elegant handling than this
ACADEMIC_YEAR='2015/2016'
NOMINAL_HOURS=1600

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
            
        return [semester1_hours, semester2_hours, semester3_hours,
            int(semester1_hours + semester2_hours + semester3_hours), len(activities)]
    
    def total_hours(self, academic_year = ACADEMIC_YEAR):
        '''Calculate the total allocated hours'''
        hours_by_semester = self.hours_by_semester(academic_year)
        return hours_by_semester[3]
            
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
    academic_year = models.CharField(max_length = 10, default = '2015/2016')
    staff = models.ForeignKey(Staff, null = True, blank = True)
    
    def __str__(self):
        return self.name + ' (' + str(self.module) + ')'
        
    def module_details(self):
        return str(self.module_id)
        
    def is_allocated(self):
        return self.staff is not None
        
    def hours_by_semester(self):
        '''Works out the hours in each semester for this activity and returns as a list'''
        
        semesters = self.semester.split(',')
        
        # First calculate the hours over all semesters
        if self.hours_percentage == self.HOURS:
            total_hours = self.hours
        else:
            total_hours = self.percentage * NOMINAL_HOURS / 100
        
        # Create a list to contain their subdivision
        split_hours = list()
        # How many semesters are listed?
        no_semesters = len(semesters)
        # We currently have three semesters, 1, 2 and 3
        for s in range(1,4):
            # Check if this one is flagged, brutally ugly code :-(
            # TODO: Try and fix the abomination 
            if self.semester.count(str(s)) > 0:
                split_hours.append(total_hours / no_semesters)
            else:
                # Nothing in this semester
                split_hours.append(0)
        
        split_hours.append(total_hours)        
        return split_hours
            
            
    class Meta:
        verbose_name_plural = "activities"
        

class Module(models.Model):
    '''Basic information about a module
    
    module_code the code for the module (e.g. EEE122)
    module_name the module name
    semester    a Comma Separated Variable list of semesters the module covers
    
    Eventually augmenting this from CMS would be useful
    '''
    
    module_code = models.CharField(max_length=10)
    module_name = models.CharField(max_length=200)
    semester = models.CommaSeparatedIntegerField(max_length=10)
    
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
    archive = models.BooleanField()
    targets = models.ManyToManyField(Staff, null=True, blank=True)
    groups = models.ManyToManyField(Group, null=True, blank=True)
    created = models.DateTimeField(auto_now_add = True)
    modified = models.DateTimeField(auto_now = True)
    
    def __str__(self):
        return self.name + ' due ' + str(self.deadline)
    
    
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
