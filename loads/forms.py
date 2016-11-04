from django import forms
from django.forms import ModelForm
from django.forms import BaseModelFormSet

from django.core.validators import RegexValidator

from .models import AssessmentResource
from .models import AssessmentResourceType
from .models import Staff
from .models import TaskCompletion
from .models import ExamTracker
from .models import CourseworkTracker
from .models import Project
from .models import WorkPackage


class MigrateWorkPackageForm(forms.Form):
    '''This form allows for material in one Work Package to another'''
    source_package = forms.ModelChoiceField(queryset=WorkPackage.objects.all())
    destination_package = forms.ModelChoiceField(queryset=WorkPackage.objects.all())
    copy_activities = forms.BooleanField(required=False)
    copy_modules = forms.BooleanField(required=False)
    copy_modulestaff = forms.BooleanField(required=False)


class LoadsByModulesForm(forms.Form):
    '''This prompts for comma separated semesters used for some restrictions'''
    semesters = forms.CharField(
        max_length=10,
        #help_text='Comma separated list of semesters to show',
        required=False,
        validators=[
            RegexValidator(
                regex='^[0-9,]*$',
                message='Semesters must be comma separated numbers',
                code='invalid_semesters'
            ),
        ]
    )
    brief_details = forms.BooleanField(
        required=False
    )

    
class AssessmentResourceForm(ModelForm):
    '''This form is used to upload an assessment resource'''
    class Meta:
        model=AssessmentResource
        # A number of fields are automatically handled
        fields = ['name', 'details', 'resource_type', 'resource']


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
        
        
        
class ProjectForm(ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'activity_type', 'body', 'start', 'end']


class BaseModuleStaffByStaffFormSet(BaseModelFormSet):
    def clean(self):
        """
        Adds validation to check that no two links have the same anchor or URL
        and that all links have both an anchor and URL.
        """
        if any(self.errors):
            return

        modules = []
        duplicates = False

        for form in self.forms:
            if form in self.deleted_forms:
                continue
                
            if form.cleaned_data:
                module = form.cleaned_data['module']

                if module in modules:
                    duplicates = True
                modules.append(module)
            
                contact_proportion = form.cleaned_data['contact_proportion']
                if contact_proportion < 0 or contact_proportion > 100:
                    raise forms.ValidationError(
                        'Contact proportion must be a valid percentage',
                        code='invalid_contact_proportion'
                    )
                    
                admin_proportion = form.cleaned_data['admin_proportion']
                if admin_proportion < 0 or admin_proportion > 100:
                    raise forms.ValidationError(
                        'Admin proportion must be a valid percentage',
                        code='invalid_admin_proportion'
                    )
                    
                assessment_proportion = form.cleaned_data['assessment_proportion']
                if assessment_proportion < 0 or assessment_proportion > 100:
                    raise forms.ValidationError(
                        'Contact proportion must be a valid percentage',
                        code='invalid_assessment_proportion'
                    )

            if duplicates:
                raise forms.ValidationError(
                    'Modules should not appear more than once.',
                    code='duplicate_modules'
                )


class BaseModuleStaffByModuleFormSet(BaseModelFormSet):
    def clean(self):
        """
        Adds validation to check that no two links have the same anchor or URL
        and that all links have both an anchor and URL.
        """
        if any(self.errors):
            return

        staff_members = []
        contact_total = 0
        admin_total = 0
        assessment_total = 0
        
        duplicates = False

        for form in self.forms:
            if form in self.deleted_forms:
                continue
                
            if form.cleaned_data:
                staff = form.cleaned_data['staff']

                if staff in staff_members:
                    duplicates = True
                staff_members.append(staff)
            
                contact_proportion = form.cleaned_data['contact_proportion']
                contact_total += contact_proportion
                if contact_proportion < 0 or contact_proportion > 100:
                    raise forms.ValidationError(
                        'Contact proportion must be a valid percentage',
                        code='invalid_contact_proportion'
                    )

                admin_proportion = form.cleaned_data['admin_proportion']
                admin_total += admin_proportion
                if admin_proportion < 0 or admin_proportion > 100:
                    raise forms.ValidationError(
                        'Admin proportion must be a valid percentage',
                        code='invalid_admin_proportion'
                    )
                    
                assessment_proportion = form.cleaned_data['assessment_proportion']
                assessment_total += assessment_proportion
                if assessment_proportion < 0 or assessment_proportion > 100:
                    raise forms.ValidationError(
                        'Contact proportion must be a valid percentage',
                        code='invalid_assessment_proportion'
                    )

            if duplicates:
                raise forms.ValidationError(
                    'Staff members should not appear more than once.',
                    code='duplicate_staff'
                )
            if contact_total > 100:
                raise forms.ValidationError(
                    'Contact proportions are over 100%',
                    code='invalid_contact_total'
                )
            if admin_total > 100:
                raise forms.ValidationError(
                    'Admin proportions are over 100%',
                    code='invalid_contact_total'
                )
            if assessment_total > 100:
                raise forms.ValidationError(
                    'Assessment proportions are over 100%',
                    code='invalid_contact_total'
                )
