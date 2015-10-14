from django.db import models

# Create your models here.

class Staff(models.Model):
    title = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    staff_number = models.CharField(max_length=20)
    fte = models.PositiveSmallIntegerField(default=100,)
    
    def __str__(self):
        return self.title + ' ' + self.first_name + ' ' + self.last_name
        
    class Meta:
        verbose_name_plural = "staff"

    
class ActivityType(models.Model):
    TEACHING = 'TEA'
    RESEARCH = 'RES'
    ENTERPRISE = 'ENT'
    ADMIN = 'ADM'
    OUTREACH ='OUT'
    CATEGORY_CHOICES = (
        (TEACHING, 'Teaching'),
        (RESEARCH, 'Research'),
        (ENTERPRISE, 'Enterprise'),
        (ADMIN, 'Admin'),
        (OUTREACH, 'Outreach'),
    )
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=3, choices=CATEGORY_CHOICES, default=TEACHING)
    
    def __str__(self):
        return self.name
    

class Activity(models.Model):
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
    semester = models.PositiveSmallIntegerField()
    activity_type = models.ForeignKey('ActivityType')
    module_id = models.ForeignKey('Module')
    
    def __str__(self):
        #module = Module.objects.get(pk = self.module_id)
        module = self.module_id
        return self.name + ' (' + str(module) + ')' + repr(self.is_allocated())
        
    def module_details(self):
        module = self.module_id
        return str(module)
        
    def is_allocated(self):
        count = StaffActivity.objects.all().filter(activity_id=self.id)
        if count:
            return True
        else:
            return False
            
    class Meta:
        verbose_name_plural = "activities"
        

class StaffActivity(models.Model):
    staff_id = models.ForeignKey('Staff')
    activity_id = models.ForeignKey('Activity')
    
    def __str__(self):
        return staff_id + ":" + activity_id


class Module(models.Model):
    module_code = models.CharField(max_length=10)
    module_name = models.CharField(max_length=200)
    semester = models.PositiveSmallIntegerField()
    
    def __str__(self):
        return self.module_code + ' : ' + self.module_name
    

# balancing...
# work out total hours for each staff member.
# scale to 100% - using FTE, but also percentages allocated (needs a crude hour conversion)
#
