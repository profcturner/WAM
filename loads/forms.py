from django import forms
from django.forms import ModelForm
from django.forms import BaseModelFormSet

from django.core.validators import RegexValidator
from django.contrib.auth.models import User, Group

from django.db import transaction
from django.core.exceptions import ValidationError

from .models import AssessmentResource
from .models import AssessmentStateSignOff
from .models import ExternalExaminer
from .models import Staff
from .models import TaskCompletion
from .models import Programme
from .models import Project
from .models import WorkPackage


class MigrateWorkPackageForm(forms.Form):
    """This form allows for material in one Work Package to another"""
    # TODO: Still really ugly, and needs some validation for impossible combinations
    source_package = forms.ModelChoiceField(queryset=WorkPackage.objects.all())
    destination_package = forms.ModelChoiceField(queryset=WorkPackage.objects.all())
    copy_programmes = forms.BooleanField(required=False, initial=True)
    copy_modules = forms.BooleanField(required=False, initial=True)
    copy_modulestaff = forms.BooleanField(required=False, initial=True, label="Copy Module Allocations")
    copy_activities_modules = forms.BooleanField(required=False, initial=True, label="Copy Module Activities")
    copy_activities_generated = forms.BooleanField(required=False, initial=True, label="Copy Generated Activities")
    copy_activities_custom = forms.BooleanField(required=False, initial=True, label="Copy Custom Activities")
    generate_projects = forms.BooleanField(required=False, initial=True)


class LoadsByModulesForm(forms.Form):
    """This prompts for comma separated semesters used for some restrictions"""
    semesters = forms.CharField(
        max_length=10,
        # help_text='Comma separated list of semesters to show',
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


class ModulesIndexForm(forms.Form):
    """This prompts for comma separated semesters used for some restrictions"""
    semesters = forms.CharField(
        max_length=10,
        # help_text='Comma separated list of semesters to show',
        required=False,
        validators=[
            RegexValidator(
                regex='^[0-9,]*$',
                message='Semesters must be comma separated numbers',
                code='invalid_semesters'
            ),
        ]
    )
    programme = forms.ModelChoiceField(queryset=Programme.objects.all(), required=False)
    lead_programme = forms.BooleanField(required=False, initial=False)
    show_people = forms.BooleanField(required=False, initial=False)



class AssessmentResourceForm(ModelForm):
    """This form is used to upload an assessment resource"""

    class Meta:
        model = AssessmentResource
        # A number of fields are automatically handled
        fields = ['name', 'details', 'resource_type', 'resource']


class StaffWorkPackageForm(ModelForm):
    """This form is to change a Staff member's active WorkPackage"""

    class Meta:
        model = Staff
        # Only one field is on the form, the rest are passed in before
        fields = ['package']


class TaskCompletionForm(ModelForm):
    """This form is to file completion of a task given an existing task"""

    class Meta:
        model = TaskCompletion
        # Only one field is on the form, the rest are passed in before
        fields = ['comment']


class ProjectForm(ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'activity_type', 'body', 'start', 'end']


class AssessmentStateSignOffForm(ModelForm):
    class Meta:
        model = AssessmentStateSignOff
        fields = ['assessment_state', 'notes', 'module', 'signed_by']
        widgets = {'module': forms.HiddenInput(), 'signed_by': forms.HiddenInput()}

    def clean(self):
        """Check the user can invoke this state"""
        assessment_state = self.cleaned_data['assessment_state']
        module = self.cleaned_data['module']
        signed_by = self.cleaned_data['signed_by']
        #staff = Staff.objects.get(user=signed_by)

        #if not assessment_state.can_be_set_by(staff, module):
        #    raise ValidationError("You don't have permission to select that state.")
        return assessment_state


class StaffCreationForm(forms.Form):
    """Allows for the creation of a Staff and linked User"""

    username = forms.CharField(label='Enter Username', min_length=4, max_length=150)
    email = forms.EmailField(label='Enter Email')
    title = forms.CharField(label='Enter Title (Dr/Prof/etc)')
    first_name = forms.CharField()
    last_name = forms.CharField()
    password1 = forms.CharField(required=False, label='Enter password', widget=forms.PasswordInput)
    password2 = forms.CharField(required=False, label='Confirm password', widget=forms.PasswordInput)
    staff_number = forms.CharField(required=False, label='Staff Number if different from username')
    groups = forms.ModelMultipleChoiceField(required=False, queryset=Group.objects.all())
    package = forms.ModelChoiceField(required=False, queryset=WorkPackage.objects.all())

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        if User.objects.filter(username=username).count():
            raise ValidationError("Username already exists")
        return username

    def clean_staff_number(self):
        # TODO: This code isn't really working... I get a KeyError if I try to access username directly...
        staff_number = self.cleaned_data['staff_number'].lower()
        username = self.cleaned_data.get('username')

        if not staff_number:
            # Fall back to the username
            staff_number = username

        if Staff.objects.filter(staff_number=staff_number).count():
            raise ValidationError("Staff number already exists")
        return staff_number

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        r = User.objects.filter(email=email)
        if r.count():
            raise ValidationError("Email already exists")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if len(password1):
            if password1 and password2 and password1 != password2:
                raise ValidationError("Password don't match")

        return password2

    @transaction.atomic
    def save(self):

        # If a staff number wasn't specified, default to username
        staff_number = self.cleaned_data.get('staff_number')

        if not self.cleaned_data.get('staff_number'):
            staff_number = self.cleaned_data.get('username')

        # Check if a password is specified, if not, we will have to set one, and later invalidate it
        # This is for users logging in via remote authentication (which will be typical in Universities)
        # Passwords should only be added if actually used (for instance, not using CAS or similar)
        if len(self.cleaned_data.get('password1')):
            no_password = False
            password = self.password1
        else:
            # auth_user always requires a password, so we'll have to invalidate it later
            no_password = True
            password = "None"

        user = User.objects.create_user(
            username=self.cleaned_data.get('username'),
            email=self.cleaned_data.get('email'),
            first_name=self.cleaned_data.get('first_name'),
            last_name=self.cleaned_data.get('last_name'),
            password=password
        )

        # Seems like auth_user requires a password no matter what, so invalidate it if not needed
        if no_password:
            user.set_unusable_password()
            user.save()

        # And now add group associations
        for group in self.cleaned_data.get('groups'):
            group.user_set.add(user)

        # And now create the linked Staff object
        Staff.objects.create(
            user=user,
            title=self.cleaned_data.get('title'),
            staff_number=staff_number,
            package=self.cleaned_data.get('package')
        )

        return user


class ExternalExaminerCreationForm(forms.Form):
    """Allows for the creation of a Staff and linked User"""

    username = forms.CharField(label='Enter Username', min_length=4, max_length=150)
    email = forms.EmailField(label='Enter Email')
    title = forms.CharField(label='Enter Title (Dr/Prof/etc)')
    first_name = forms.CharField()
    last_name = forms.CharField()
    password1 = forms.CharField(required=False, label='Enter password', widget=forms.PasswordInput)
    password2 = forms.CharField(required=False, label='Confirm password', widget=forms.PasswordInput)
    staff_number = forms.CharField(required=False, label='Staff Number if different from username')
    package = forms.ModelChoiceField(required=False, queryset=WorkPackage.objects.all())

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        if User.objects.filter(username=username).count():
            raise ValidationError("Username already exists")
        return username

    def clean_staff_number(self):
        # TODO: This code isn't really working... I get a KeyError if I try to access username directly...
        staff_number = self.cleaned_data['staff_number'].lower()
        username = self.cleaned_data.get('username')

        if not staff_number:
            # Fall back to the username
            staff_number = username

        if Staff.objects.filter(staff_number=staff_number).count():
            raise ValidationError("Staff number already exists")
        return staff_number

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        r = User.objects.filter(email=email)
        if r.count():
            raise ValidationError("Email already exists")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if len(password1):
            if password1 and password2 and password1 != password2:
                raise ValidationError("Password don't match")

        return password2

    @transaction.atomic
    def save(self):

        # If a staff number wasn't specified, default to username
        staff_number = self.cleaned_data.get('staff_number')

        if not self.cleaned_data.get('staff_number'):
            staff_number = self.cleaned_data.get('username')

        # Check if a password is specified, if not, we will have to set one, and later invalidate it
        # This is for users logging in via remote authentication (which will be typical in Universities)
        # Passwords should only be added if actually used (for instance, not using CAS or similar)
        if len(self.cleaned_data.get('password1')):
            no_password = False
            password = self.password1
        else:
            # auth_user always requires a password, so we'll have to invalidate it later
            no_password = True
            password = "None"

        user = User.objects.create_user(
            username=self.cleaned_data.get('username'),
            email=self.cleaned_data.get('email'),
            first_name=self.cleaned_data.get('first_name'),
            last_name=self.cleaned_data.get('last_name'),
            password=password
        )

        # Seems like auth_user requires a password no matter what, so invalidate it if not needed
        if no_password:
            user.set_unusable_password()
            user.save()

        # And now create the linked External Examiner object
        Staff.objects.create(
            user=user,
            is_external=True,
            title=self.cleaned_data.get('title'),
            staff_number=staff_number,
            package=self.cleaned_data.get('package')
        )

        return user


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
            # If the form is deleted, don't validate, it's data is about to be nuked
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
            # If the form is deleted, don't validate, it's data is about to be nuked
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
