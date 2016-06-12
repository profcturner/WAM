from django import forms
from django.forms import ModelForm

from .models import Staff
from .models import TaskCompletion
from .models import ExamTracker
from .models import CourseworkTracker

class StaffWorkPackageForm(ModelForm):
    '''This form is to change a Staff member's active WorkPackage'''
    class Meta:
        model = Staff
        # Only one field is on the form, the rest are passed in before
        fields = ['package']
        
        
class TaskCompletionForm(ModelForm):
    '''This form is to file completion of a task given an existing task'''
    class Meta:
        model = TaskCompletion
        # Only one field is on the form, the rest are passed in before
        fields = ['comment']
        
        
class ExamTrackerForm(ModelForm):
    '''This form is to file progression of an Exam paper through QA processes'''
    class Meta:
        model = ExamTracker
        # Only one field is on the form, the rest are passed in before
        fields = ['progress']
        
        
class CourseworkTrackerForm(ModelForm):
    '''This form is to file progression of Coursework through QA processes'''
    class Meta:
        model = CourseworkTracker
        # Only one field is on the form, the rest are passed in before
        fields = ['progress']
        