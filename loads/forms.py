from django import forms
from django.forms import ModelForm

from .models import Staff
from .models import TaskCompletion
from .models import ExamTracker
from .models import CourseworkTracker
from .models import WorkPackage

class MigrateWorkPackageForm(forms.Form):
    '''This form allows for material in one Work Package to another'''
    source_package = forms.ModelChoiceField(queryset=WorkPackage.objects.all())
    destination_package = forms.ModelChoiceField(queryset=WorkPackage.objects.all())
    copy_activities = forms.BooleanField(required=False)
    copy_modules = forms.BooleanField(required=False)
    copy_modulestaff = forms.BooleanField(required=False)

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
        