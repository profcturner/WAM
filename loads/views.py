import os
import mimetypes
import logging

from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.forms import modelformset_factory
from django.contrib import messages

from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.core.exceptions import PermissionDenied

# Class Views
from django.views.generic import ListView
from django.views.generic import UpdateView, CreateView

from django.views import View

# Permission decorators
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from .decorators import staff_only, external_only, admin_only
from django.utils.decorators import method_decorator

# Create your views here.

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect

from django.template import RequestContext, loader

from django.contrib.auth.models import User, Group

from .models import ActivityGenerator, Category
from .models import AssessmentResource
from .models import AssessmentStaff
from .models import AssessmentState
from .models import AssessmentStateSignOff
from .models import ExternalExaminer
from .models import Staff
from .models import Task
from .models import Activity
from .models import TaskCompletion
from .models import Module
from .models import ModuleStaff
from .models import Programme
from .models import Project
from .models import ProjectStaff
from .models import WorkPackage

from .forms import AssessmentResourceForm
from .forms import AssessmentStateSignOffForm
from .forms import LoadsByModulesForm
from .forms import TaskCompletionForm
from .forms import StaffWorkPackageForm
from .forms import MigrateWorkPackageForm
from .forms import ModulesIndexForm
from .forms import ProjectForm
from .forms import StaffCreationForm
from .forms import ExternalExaminerCreationForm
from .forms import BaseModuleStaffByModuleFormSet
from .forms import BaseModuleStaffByStaffFormSet

from operator import itemgetter

# Get an instance of a logger
logger = logging.getLogger(__name__)

def index(request):
    """Main index page for non admin views"""

    template = loader.get_template('loads/index.html')
    context = {
        'home_page': True,
    }
    logger.debug("Visiting home page")
    return HttpResponse(template.render(context, request))

@external_only
def external_index(request):
    """The main home page for External Examiners"""

    template = loader.get_template('loads/external/index.html')
    context = {
        'home_page': True,
    }
    return HttpResponse(template.render(context, request))


def forbidden(request):
    """General permissions failure warning"""

    template = loader.get_template('loads/forbidden.html')

    return HttpResponse(template.render({}, request))


def logged_out(request):
    """Show that we are logged out"""

    template = loader.get_template('loads/logged_out.html')

    return HttpResponse(template.render({}, request))


@login_required
def download_assessment_resource(request, resource_id):
    """Download an assessment resource"""
    # Get the resource object
    resource = get_object_or_404(AssessmentResource, pk=resource_id)

    # Fetch the staff user associated with the person requesting
    try:
        staff = Staff.objects.get(user=request.user)
    except Staff.DoesNotExist:
        staff = None

    if not staff:
        return HttpResponseRedirect(reverse('forbidden'))

    permission = resource.is_downloadable_by(staff)

    if not permission:
        return HttpResponseRedirect(reverse('forbidden'))

    resource.downloads += 1
    resource.save()

    # Get the base filename, and try and work out the type
    filename = os.path.basename(resource.resource.name)
    file_mimetype = mimetypes.guess_type(filename)[0]

    # Start a response
    response = HttpResponse(resource.resource.file, content_type=file_mimetype)

    # Let's suggest the filename
    response['Content-Disposition'] = 'inline; filename="%s"' % filename
    response['Content-Length'] = len(resource.resource.file)
    return response


@login_required
def delete_assessment_resource(request, resource_id, confirm=None):
    """Delete an assessment resource, should not be possible for signed resources, except for superuser"""
    # Get the resource object
    resource = get_object_or_404(AssessmentResource, pk=resource_id)

    # TODO: this is none too elegant, and could be outsourced
    # Fetch the staff user associated with the person requesting
    try:
        staff = Staff.objects.get(user=request.user)
    except Staff.DoesNotExist:
        staff = None

    # If neither here, time to boot
    if not staff:
        return HttpResponseRedirect(reverse('forbidden'))

    # Assume a lack of permissions
    permission = False

    # If the resource is signed, deletions are forbidden except for superuser
    signed = len(AssessmentStateSignOff.objects.all().filter(module=resource.module). \
                 filter(created__gt=resource.created))

    if signed:
        if staff and staff.user.is_superuser:
            permission = True
    else:
        # Unsigned resources can be deleted, by owners and module coordinators
        if resource.owner == staff or resource.module.coordinator == staff:
            permission = True

    if not permission:
        return HttpResponseRedirect(reverse('forbidden'))

    # Ok, we are allowed to delete
    # Check if the deletion is confirmed
    if not confirm:
        context = {
            'resource': resource
        }
        template = loader.get_template('loads/modules/delete_assessment_resource.html')
        return HttpResponse(template.render(context, request))

    # If we are still here we can delete safely
    resource.delete()

    url = reverse('modules_details', kwargs={'module_id': resource.module_id})
    return HttpResponseRedirect(url)


@login_required
@staff_only
def loads(request):
    """Show the loads for all members of staff"""

    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package

    # If the staff member is a superuser just check the workpackage exists
    if staff.user.is_superuser:
        if not package:
            url = reverse('workpackage_change')
            return HttpResponseRedirect(url)
    else:
        # or it's set to a package they are not "in" send them to the chooser
        if not package or package not in staff.get_all_packages():
            #TODO: Probably really want to 403 this...
            url = reverse('workpackage_change')
            return HttpResponseRedirect(url)

    # This controls whether hours or percentages are shown
    show_percentages = package.show_percentages

    total = 0.0
    total_staff = 0
    group_data = []

    # Go through each group in turn
    for group in package.groups.all():
        group_list = []
        group_size = 0
        group_total = 0.0
        group_average = 0.0
        group_allocated_staff = 0
        group_allocated_average = 0.0
        # Get the users in the group
        users = User.objects.all().filter(groups__in=[group]).distinct().order_by('last_name')
        # And the associated staff objects
        staff_list = Staff.objects.all().filter(user__in=users).order_by('user__last_name')
        for staff in staff_list:
            load_info = staff.hours_by_semester(package=package)
            # Note below: the reason for checking any load as will as conditions is to allow
            # colleagues to appear in other workpackages in times they had an allocated load, even
            # if they are now inactive or flagged as having no workload

            # Check any staff member with no load is active, if not, skip them
            if not staff.is_active() and load_info[0] == 0:
                continue
            # If this colleague isn't flagged as having a workload and doesn't have any, also skip
            if not staff.has_workload and load_info[0] ==0:
                continue

            # Ok, we should include this colleague
            if show_percentages:
                combined_item = [staff, 100 * load_info[0] / package.nominal_hours,
                                 100 * load_info[1] / package.nominal_hours,
                                 100 * load_info[2] / package.nominal_hours,
                                 100 * load_info[3] / package.nominal_hours,
                                 100 * (100 * load_info[0] / staff.fte) / package.nominal_hours]
            else:
                combined_item = [staff, load_info[0], load_info[1], load_info[2], load_info[3],
                                 100 * load_info[0] / staff.fte]
            group_list.append(combined_item)
            group_total += load_info[0]
            group_size += 1
            if load_info[0]:
                # Also count staff with allocated hours
                group_allocated_staff += 1
        if group_size:
            group_average = group_total / group_size
        if group_allocated_staff:
            group_allocated_average = group_total / group_allocated_staff
        group_data.append(
            [group, group_list, group_total, group_average, group_allocated_staff, group_allocated_average])
        total += group_total
        total_staff += len(staff_list)

    if total_staff:
        average = total / total_staff
    else:
        average = 0

    logger.debug("%s: Loads by staff viewed", request.user, extra={'package': package})
    template = loader.get_template('loads/loads.html')
    context = {
        'group_data': group_data,
        'total': total,
        'average': average,
        'package': package,
        'show_percentages': show_percentages,
        'loads_menu': True,
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
def loads_by_staff_chart(request):
    """Show a graph of the loads for all members of staff in a group"""
    # We might want to use this example.
    # https://crinkles.dev/writing/css-only-stacked-bar-chart/

    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package

    # We will likely want this to be configurable
    sort_lists = True

    # If either the workpackage for the member of staff is undefined
    # or it's set to a package they are not "in" send them to the chooser
    #if not package or package not in staff.get_all_packages():
    #    url = reverse('workpackage_change')
    #    return HttpResponseRedirect(url)

    # This controls whether hours or percentages are shown
    #show_percentages = package.show_percentages

    # If the staff member is a superuser just check the workpackage exists
    if staff.user.is_superuser:
        if not package:
            url = reverse('workpackage_change')
            return HttpResponseRedirect(url)
    else:
        # or it's set to a package they are not "in" send them to the chooser
        if not package or package not in staff.get_all_packages():
            #TODO: Probably really want to 403 this...
            url = reverse('workpackage_change')
            return HttpResponseRedirect(url)

    # This controls whether hours or percentages are shown
    show_percentages = package.show_percentages
    show_percentages = True

    total = 0.0
    total_staff = 0
    group_data = []

    # Go through each group in turn
    for group in package.groups.all():
        group_list = []
        group_size = 0
        group_total = 0.0
        group_average = 0.0
        group_allocated_staff = 0
        group_allocated_average = 0.0
        # Get the users in the group
        users = User.objects.all().filter(groups__in=[group]).distinct().order_by('last_name')
        # And the associated staff objects
        staff_list = Staff.objects.all().filter(user__in=users).order_by('user__last_name')
        for staff in staff_list:
            staff_load_by_category = staff.hours_by_type(package=package)

            # Note below: the reason for checking any load as will as conditions is to allow
            # colleagues to appear in other workpackages in times they had an allocated load, even
            # if they are now inactive or flagged as having no workload

            hours = sum(staff_load_by_category.values())
            #hours = 10
            # Check any staff member with no load is active, if not, skip them
            if not staff.is_active() and hours == 0:
                continue
            # If this colleague isn't flagged as having a workload and doesn't have any, also skip
            if not staff.has_workload and hours ==0:
                continue

            combined_item = [staff, staff_load_by_category, hours]
            group_list.append(combined_item)
            group_total += hours
            group_size += 1
            if hours !=0:
                # Also count staff with allocated hours
                group_allocated_staff += 1
        if group_size:
            group_average = group_total / group_size
        if group_allocated_staff:
            group_allocated_average = group_total / group_allocated_staff

        if sort_lists:
            group_list = sorted(group_list, key=lambda item : item[2], reverse=True)

        group_data.append(
            [group, group_list, group_total, group_average, group_allocated_staff, group_allocated_average])
        total += group_total
        total_staff += len(staff_list)

    if total_staff:
        average = total / total_staff
    else:
        average = 0

    logger.debug("%s: Loads by staff chart viewed", request.user, extra={'package': package})
    template = loader.get_template('loads/loads_charts.html')
    context = {
        'group_data': group_data,
        'total': total,
        'average': average,
        'package': package,
        'categories': Category.objects.all(),
        'show_percentages': show_percentages,
        'loads_menu': True,
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
def loads_modules(request, semesters, staff_details=False):
    """Shows allocation information by modules"""
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package
    modules = Module.objects.all().filter(package=package).order_by('module_code')

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request
        form = LoadsByModulesForm(request.POST)

        # check whether it's valid:
        if form.is_valid():
            semesters = form.cleaned_data['semesters']
            brief_details = form.cleaned_data['brief_details']

    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = LoadsByModulesForm()
        # If semesters came via get, let's populate the form
        form.fields['semesters'].initial = semesters
        brief_details = False

    # Check for any semester limitations, split by comma if something is actually there
    if semesters:
        valid_semesters = semesters.split(',')
    else:
        valid_semesters = list()

    combined_list = []
    for module in modules:
        # Is it valid for the semester, i.e. are and of its semesters in the passed in one?
        if len(valid_semesters):
            module_semesters = module.semester.split(',')
            valid_semester = False
            for m_sem in module_semesters:
                for v_sem in valid_semesters:
                    if m_sem == v_sem:
                        valid_semester = True
            if not valid_semester:
                continue

        # Get Allocation information
        module_staff = ModuleStaff.objects.all().filter(module=module)
        contact_proportion = 0
        admin_proportion = 0
        assessment_proportion = 0
        extra_hours = 0
        for allocation in module_staff:
            contact_proportion += allocation.contact_proportion
            admin_proportion += allocation.admin_proportion
            assessment_proportion += allocation.assessment_proportion

        activities = Activity.objects.all().filter(module=module)
        for activity in activities:
            hours_per_semester = activity.hours_by_semester()
            extra_hours += hours_per_semester[0]

        module_info = [module,
                       module.get_contact_hours(),
                       contact_proportion,
                       module.get_admin_hours(),
                       admin_proportion,
                       module.get_assessment_hours(),
                       assessment_proportion,
                       extra_hours,
                       module_staff]

        combined_list.append(module_info)

    logger.debug("%s: Loads by modules viewed", request.user, extra={'package': package})
    template = loader.get_template('loads/loads/modules.html')
    context = {
        'form': form,
        'brief_details': brief_details,
        'valid_semesters': valid_semesters,
        'combined_list': combined_list,
        'package': package,
        'loads_menu': True,
        'staff_details': staff_details,
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
def activities(request, staff_id):
    """Show the activities for a given staff member"""
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package

    show_percentages = package.show_percentages

    # Now the staff member we want to look at
    staff = get_object_or_404(Staff, pk=staff_id)
    activities = Activity.objects.all().filter(staff=staff).filter(package=package).order_by('name')
    combined_list = []
    combined_list_modules = []
    total = 0.0
    semester1_total = 0.0
    semester2_total = 0.0
    semester3_total = 0.0

    for activity in activities:
        load_info = activity.hours_by_semester()
        if show_percentages:
            combined_item = [activity,
                             100 * load_info[0] / package.nominal_hours,
                             100 * load_info[1] / package.nominal_hours,
                             100 * load_info[2] / package.nominal_hours,
                             100 * load_info[3] / package.nominal_hours]
        else:
            combined_item = [activity, load_info[0], load_info[1], load_info[2], load_info[3]]
        combined_list.append(combined_item)
        semester1_total += load_info[1]
        semester2_total += load_info[2]
        semester3_total += load_info[3]
        total += load_info[0]

    # Add hours calculated from "automatic" module allocation
    modulestaff = ModuleStaff.objects.all().filter(staff=staff_id).filter(package=package)
    for moduledata in modulestaff:
        c_hours = moduledata.module.get_contact_hours_by_semester()
        as_hours = moduledata.module.get_assessment_hours_by_semester()
        ad_hours = moduledata.module.get_admin_hours_by_semester()

        semester1_c_hours = c_hours[1] * moduledata.contact_proportion / 100
        semester1_as_hours = as_hours[1] * moduledata.assessment_proportion / 100
        semester1_ad_hours = ad_hours[1] * moduledata.admin_proportion / 100

        semester2_c_hours = c_hours[2] * moduledata.contact_proportion / 100
        semester2_as_hours = as_hours[2] * moduledata.assessment_proportion / 100
        semester2_ad_hours = ad_hours[2] * moduledata.admin_proportion / 100

        semester3_c_hours = c_hours[3] * moduledata.contact_proportion / 100
        semester3_as_hours = as_hours[3] * moduledata.assessment_proportion / 100
        semester3_ad_hours = ad_hours[3] * moduledata.admin_proportion / 100

        c_hours_proportion = c_hours[0] * moduledata.contact_proportion / 100
        as_hours_proportion = as_hours[0] * moduledata.assessment_proportion / 100
        ad_hours_proportion = ad_hours[0] * moduledata.admin_proportion / 100

        if show_percentages:
            combined_item = [str(moduledata.module) + ' Contact Hours',
                             100 * c_hours_proportion / package.nominal_hours,
                             100 * semester1_c_hours / package.nominal_hours,
                             100 * semester2_c_hours / package.nominal_hours,
                             100 * semester3_c_hours / package.nominal_hours]
        else:
            combined_item = [str(moduledata.module) + ' Contact Hours', c_hours_proportion,
                             semester1_c_hours, semester2_c_hours, semester3_c_hours]
        combined_list_modules.append(combined_item)

        if show_percentages:
            combined_item = [str(moduledata.module) + ' Admin Hours',
                             100 * ad_hours_proportion / package.nominal_hours,
                             100 * semester1_ad_hours / package.nominal_hours,
                             100 * semester2_ad_hours / package.nominal_hours,
                             100 * semester3_ad_hours / package.nominal_hours]

        else:
            combined_item = [str(moduledata.module) + ' Admin Hours', ad_hours_proportion,
                             semester1_ad_hours, semester2_ad_hours, semester3_ad_hours]
        combined_list_modules.append(combined_item)

        if show_percentages:
            combined_item = [str(moduledata.module) + ' Assessment Hours',
                             100 * as_hours_proportion / package.nominal_hours,
                             100 * semester1_as_hours / package.nominal_hours,
                             100 * semester2_as_hours / package.nominal_hours,
                             100 * semester3_as_hours / package.nominal_hours]

        else:
            combined_item = [str(moduledata.module) + ' Assessment Hours', as_hours_proportion,
                             semester1_as_hours, semester2_as_hours, semester3_as_hours]
        combined_list_modules.append(combined_item)

        semester1_total += (semester1_c_hours + semester1_ad_hours + semester1_as_hours)
        semester2_total += (semester2_c_hours + semester2_ad_hours + semester2_as_hours)
        semester3_total += (semester3_c_hours + semester3_ad_hours + semester3_as_hours)

        # if show_percentages:
        #    semester1_total = semester1_total * 100 / package.nominal_hours
        #    semester2_total = semester2_total * 100 / package.nominal_hours
        #    semester3_total = semester3_total * 100 / package.nominal_hours

        total += c_hours_proportion + as_hours_proportion + ad_hours_proportion

    if show_percentages:
        semester1_total = semester1_total * 100 / package.nominal_hours
        semester2_total = semester2_total * 100 / package.nominal_hours
        semester3_total = semester3_total * 100 / package.nominal_hours
        total = 100 * total / package.nominal_hours

    logger.debug("%s: Activities viewed", request.user, extra={'package': package})
    template = loader.get_template('loads/activities.html')
    context = {
        'staff': staff,
        'combined_list': combined_list,
        'combined_list_modules': combined_list_modules,
        'semester1_total': semester1_total,
        'semester2_total': semester2_total,
        'semester3_total': semester3_total,
        'total': total,
        'package': package,
        'show_percentages': show_percentages
    }
    return HttpResponse(template.render(context, request))


@login_required
def tasks_index(request):
    """Obtains a list of all non archived tasks"""
    # Fetch the tasks assigned against the specific user of the staff member
    staff = get_object_or_404(Staff, user=request.user)
    tasks = staff.get_all_tasks()
    # tasks = Task.objects.all().exclude(archive=True).order_by('deadline')

    augmented_tasks = []
    for task in tasks:
        augmented_tasks.append([task, task.is_urgent(), task.is_overdue()])

    logger.debug("%s: Tasks viewed", request.user)
    template = loader.get_template('loads/tasks/index.html')
    context = {
        'augmented_tasks': augmented_tasks,
        'tasks_menu': True,
        'archived': False
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
def archived_tasks_index(request):
    """Obtains a list of all non archived tasks"""
    # Fetch the tasks assigned against the specific user of the staff member
    staff = get_object_or_404(Staff, user=request.user)
    tasks = staff.get_all_tasks(archived=True)
    # tasks = Task.objects.all().exclude(archive=True).order_by('deadline')

    augmented_tasks = []
    for task in tasks:
        augmented_tasks.append([task, task.is_urgent(), task.is_overdue()])

    logger.debug("%s: Archived Tasks viewed", request.user)
    template = loader.get_template('loads/tasks/index.html')
    context = {
        'augmented_tasks': augmented_tasks,
        'tasks_menu': True,
        'archived': True
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
def tasks_bystaff(request, staff_id):
    """Show the tasks assigned against the specific user of the staff member"""
    staff = get_object_or_404(Staff, pk=staff_id)
    all_tasks = staff.get_all_tasks()

    # We will create separate lists for those tasks that are complete
    combined_list_complete = []
    combined_list_incomplete = []

    for task in all_tasks:
        # Is it complete? Look for a completion model
        completion = TaskCompletion.objects.all().filter(staff=staff).filter(task=task)
        if len(completion) == 0:
            combined_item = [task, task.is_urgent(), task.is_overdue()]
            combined_list_incomplete.append(combined_item)
        else:
            combined_item = [task, completion[0].when]
            combined_list_complete.append(combined_item)

    logger.debug("%s: Tasks for %s viewed", request.user, staff, extra={'package': package})
    template = loader.get_template('loads/tasks/bystaff.html')
    context = {
        'staff': staff,
        'combined_list_complete': combined_list_complete,
        'combined_list_incomplete': combined_list_incomplete,
    }
    return HttpResponse(template.render(context, request))


@login_required()
def tasks_details(request, task_id):
    """Obtains a list of all completions for a given task"""
    # Get the task itself, and all targetted users
    task = get_object_or_404(Task, pk=task_id)
    all_targets = task.get_all_targets()

    combined_list_complete = []
    combined_list_incomplete = []

    for target in all_targets:
        # Is it complete? Look for a completion model
        completion = TaskCompletion.objects.all().filter(staff=target).filter(task=task)
        if len(completion) == 0:
            # Not complete, but only add the target if they aren't active
            if target.is_active():
                combined_item = [target, False]
                combined_list_incomplete.append(combined_item)
        else:
            combined_item = [target, completion[0]]
            combined_list_complete.append(combined_item)

    total_number = len(combined_list_complete) + len(combined_list_incomplete)
    if total_number > 0:
        percentage_complete = 100 * len(combined_list_complete) / total_number
    else:
        percentage_complete = 0

    logger.debug("%s:Task details viewed %s", request.user, task, extra={'package': package})
    template = loader.get_template('loads/tasks/details.html')
    context = {
        'task': task,
        'overdue': task.is_overdue(),
        'urgent': task.is_urgent(),
        'combined_list_complete': combined_list_complete,
        'combined_list_incomplete': combined_list_incomplete,
        'percentage_complete': percentage_complete
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
@admin_only
def custom_admin_index(request):
    """The beginnings of a more integrated admin menu"""

    logger.debug("%s: Custom Admin Menu viewed", request.user)
    template = loader.get_template('loads/admin/index.html')
    return HttpResponse(template.render({}, request))


@login_required
@staff_only
@admin_only
@permission_required('loads.add_staff')
def create_staff_user(request):
    """Allows for the creation of a Staff and linked User object"""

    if request.method == 'POST':
        form = StaffCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully')

            logger.info("%s: created a staff user", request.user, extra={'form': form})
            url = reverse('custom_admin_index')
            return HttpResponseRedirect(url)

    else:
        form = StaffCreationForm()

    return render(request, 'loads/admin/create_staff_user.html', {'form': form})


@login_required
@staff_only
@admin_only
@permission_required('loads.add_externalexaminer')
def create_external_examiner(request):
    """Allows for the creation of an Examiner and linked User object"""

    if request.method == 'POST':
        form = ExternalExaminerCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully')
            logger.info("%s: created an External Examiner user", request.user, extra={'form': form})

            url = reverse('custom_admin_index')
            return HttpResponseRedirect(url)

    else:
        form = ExternalExaminerCreationForm()

    return render(request, 'loads/admin/create_external_examiner.html', {'form': form})


@login_required
@staff_only
def tasks_completion(request, task_id, staff_id):
    """Processes recording of a task completion"""
    # Get the task itself, and all targetted users
    # TODO: check for existing completions
    # TODO: check staff is in *open* targets
    task = get_object_or_404(Task, pk=task_id)
    staff = get_object_or_404(Staff, pk=staff_id)
    all_targets = task.get_all_targets()

    # check the staff member is that currently logged in
    # or a user with permission to edit completions
    is_current_user = (request.user == staff.user)
    can_override = request.user.has_perm('loads.add_taskcompletion')
    if not (is_current_user or can_override):
        return HttpResponseRedirect(reverse('forbidden'))

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = TaskCompletionForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            new_item = form.save(commit=False)
            new_item.task = task
            new_item.staff = staff

            new_item.save()
            form.save_m2m()
            logger.info("%s: masked task %s complete for %s", request.user, task, staff, extra={'form': form})

            # redirect to the task details
            # TODO: which is a pain if we came from the bystaff view
            url = reverse('tasks_details', kwargs={'task_id': task_id})
            return HttpResponseRedirect(url)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = TaskCompletionForm()

    return render(request, 'loads/tasks/completion.html', {'form': form, 'task': task,
                                                           'overdue': task.is_overdue(),
                                                           'urgent': task.is_urgent(), 'staff': staff})


@login_required
@staff_only
def add_assessment_resource(request, module_id):
    """Provide a form for uploading a module resource"""
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # Get the module itself
    module = get_object_or_404(Module, pk=module_id)

    # Check for a valid permission at this stage
    # can_override = request.user.has_perm('loads.add_assessment_resource')
    # if not can_override:
    #    return HttpResponseRedirect(reverse('forbidden'))

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request
        form = AssessmentResourceForm(request.POST, request.FILES)

        # check whether it's valid:
        if form.is_valid():
            new_item = form.save(commit=False)
            new_item.owner = staff
            new_item.module = module

            new_item.save()
            form.save_m2m()
            logger.info("%s: added as assessment resource for module %s", request.user, module)

            url = reverse('modules_details', kwargs={'module_id': module_id})
            return HttpResponseRedirect(url)


    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = AssessmentResourceForm()

    return render(request, 'loads/modules/add_assessment_resource.html',
                  {'form': form, 'staff': staff, 'module': module})


@login_required
@staff_only
def module_staff_allocation(request, module_id, package_id):
    """Edit the allocation of staff to a module member"""

    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)
    # And the module we are going to act on
    module = get_object_or_404(Module, pk=module_id)
    # And the package we are going to act on
    package = get_object_or_404(WorkPackage, pk=package_id)

    # If either the logged in user or target user aren't in the package, this is forbidden
    if package not in user_staff.get_all_packages():
        return HttpResponseRedirect(reverse('forbidden'))

    # The logged in user should be able to do this via the Admin interface, or disallow.
    permission = request.user.has_perm('loads.add_modulestaff') and request.user.has_perm(
        'loads.change_modulestaff') and request.user.has_perm('loads.delete_modulestaff')

    if not permission:
        return HttpResponseRedirect(reverse('forbidden'))

    # Get a formset with only the choosable fields
    AllocationFormSet = modelformset_factory(ModuleStaff, formset=BaseModuleStaffByModuleFormSet,
                                             fields=('staff', 'contact_proportion', 'admin_proportion',
                                                     'assessment_proportion'),
                                             can_delete=True)

    if request.method == "POST":
        formset = AllocationFormSet(
            request.POST, request.FILES,
            queryset=ModuleStaff.objects.filter(package=package).filter(module=module).order_by(
                'staff__user__last_name')
        )
        # We need to tweak the queryset to only allow staff in the package
        for form in formset:
            form.fields['staff'].queryset = package.get_all_staff()
        if formset.is_valid():
            formset.save(commit=False)
            for form in formset:
                # Some fields are missing, so don't do a full save yet
                allocation = form.save(commit=False)
                # Fix the fields
                allocation.module = module
                allocation.package = package
            # Now do a real save
            formset.save(commit=True)
            logger.info("%s: adjusted the module allocation for module %s", request.user, module, extra={'form': form})

            # redirect to the activites page
            # TODO this might just be a different package from this one, note.

            url = reverse('modules_details', args=[module_id])
            return HttpResponseRedirect(url)
    else:
        formset = AllocationFormSet(queryset=ModuleStaff.objects.filter(package=package).filter(module=module).order_by(
            'staff__user__last_name'))
        # Again, only allow staff members in the package
        for form in formset:
            form.fields['staff'].queryset = package.get_all_staff()

    return render(request, 'loads/modules/allocations.html', {'module': module, 'package': package, 'formset': formset})


@login_required
@staff_only
def modules_index(request, semesters):
    """Shows a high level list of modules"""
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package

    # By default, no programme or lead programme filter is set
    programme = None
    lead_programme = None
    # Don't show people by default
    show_people = False


    # Get all the modules in the package, pending further filtering
    modules = Module.objects.all().filter(package=package).order_by('module_code')

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request
        form = ModulesIndexForm(request.POST)
        form.fields['programme'].queryset = Programme.objects.all().filter(package=package)

        # check whether it's valid:
        if form.is_valid():
            semesters = form.cleaned_data['semesters']
            programme = form.cleaned_data['programme']
            lead_programme = form.cleaned_data['lead_programme']
            show_people = form.cleaned_data['show_people']

    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = ModulesIndexForm()
        # If semesters came via get, let's populate the form
        form.fields['semesters'].initial = semesters
        form.fields['programme'].queryset = Programme.objects.all().filter(package=package)


        # Check for any semester limitations, split by comma if something is actually there
    if semesters:
        valid_semesters = semesters.split(',')
    else:
        valid_semesters = list()


    combined_list = []
    for module in modules:
        # If there's a selected programme and this module isn't it, then skip
        if programme and module not in programme.modules.all():
            continue
        # And skip if lead programme is set, and this isn't the lead programme
        if programme and lead_programme and not (module.lead_programme == programme):
            continue
        # Is it valid for the semester, i.e. are and of its semesters in the passed in one?
        if len(valid_semesters):
            module_semesters = module.semester.split(',')
            valid_semester = False
            for m_sem in module_semesters:
                for v_sem in valid_semesters:
                    if m_sem == v_sem:
                        valid_semester = True
            if not valid_semester:
                continue

        # Store all relationships to the modules
        relationship = []

        # Is the logged in user on the teaching team?
        module_staff = ModuleStaff.objects.all().filter(module=module).filter(staff=staff)
        if len(module_staff):
            relationship.append('team_member')

        # Is the logged in user a moderator?
        if staff in module.moderators.all():
            relationship.append('moderator')

        # get the most recent assessment resource
        resources = AssessmentResource.objects.all().filter(module=module).order_by('-created')[:1]
        signoffs = AssessmentStateSignOff.objects.all().filter(module=module).order_by('-created')[:1]

        if len(resources) > 0:
            resource = resources[0]
        else:
            resource = False

        # Can the logged in user set a new assessment state?
        action_possible = False
        if len(signoffs) > 0:
            signoff = signoffs[0]
            for state in signoff.assessment_state.next_states.all():
                if state.can_be_set_by_staff(staff, module):
                    action_possible = True
        else:
            signoff = False

        combined_item = [module, relationship, resource, signoff, action_possible, module.get_lead_examiners()]
        combined_list.append(combined_item)

    logger.debug("%s: visited the Modules Index for package %s", request.user, package, extra={'form': form})
    template = loader.get_template('loads/modules/index.html')
    context = {
        'form': form,
        'combined_list': combined_list,
        'valid_semesters': valid_semesters,
        'package': package,
        'programme': programme,
        'lead_programme': lead_programme,
        'show_people': show_people,
    }
    return HttpResponse(template.render(context, request))


@login_required
@external_only
def external_modules_index(request, semesters):
    """Shows a high level list of modules to an external examiner"""
    # Fetch the staff user associated with the person requesting
    external = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = external.package

    # By default, no programme or lead programme filter is set
    programme = None
    lead_programme = None
    # Don't show people by default
    show_people = False

    # Get the list of programmes that they examine
    examined_programmes = external.get_examined_programmes()

    # Get all the modules in the package, pending further filtering
    modules = Module.objects.all().filter(package=package).order_by('module_code')

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request
        form = ModulesIndexForm(request.POST)
        form.fields['programme'].queryset = examined_programmes

        # check whether it's valid:
        if form.is_valid():
            semesters = form.cleaned_data['semesters']
            programme = form.cleaned_data['programme']
            lead_programme = form.cleaned_data['lead_programme']
            show_people = form.cleaned_data['show_people']


    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = ModulesIndexForm()
        # If semesters came via get, let's populate the form
        form.fields['semesters'].initial = semesters
        form.fields['programme'].queryset = examined_programmes


        # Check for any semester limitations, split by comma if something is actually there
    if semesters:
        valid_semesters = semesters.split(',')
    else:
        valid_semesters = list()

    combined_list = []
    for module in modules:
        # Controversial... filter out modules not relevant
        if not external.can_examine_module(module):
            continue
        # If there's a selected programme and this module isn't it, then skip
        if programme and module not in programme.modules.all():
            continue
        # And skip if lead programme is set, and this isn't the lead programme
        if programme and lead_programme and not (module.lead_programme == programme):
            continue
        # Is it valid for the semester, i.e. are and of its semesters in the passed in one?
        if len(valid_semesters):
            module_semesters = module.semester.split(',')
            valid_semester = False
            for m_sem in module_semesters:
                for v_sem in valid_semesters:
                    if m_sem == v_sem:
                        valid_semester = True
            if not valid_semester:
                continue

        # Store all relationships to the modules
        relationship = []

        if module.lead_programme in examined_programmes:
            relationship.append('lead_external')
            # That's good enough, don't bother checking for other relations
        else:
            if any(programme in examined_programmes for programme in module.programmes.all()):
                relationship.append('external')

        # get the most recent assessment resource
        resources = AssessmentResource.objects.all().filter(module=module).order_by('-created')[:1]
        signoffs = AssessmentStateSignOff.objects.all().filter(module=module).order_by('-created')[:1]

        if len(resources) > 0:
            resource = resources[0]
        else:
            resource = False

        # Can the logged in user set a new assessment state?
        action_possible = False
        if len(signoffs) > 0:
            signoff = signoffs[0]
            for state in signoff.assessment_state.next_states.all():
                if state.can_be_set_by_external(external, module):
                    action_possible = True
        else:
            signoff = False

        combined_item = [module, relationship, resource, signoff, action_possible, module.get_lead_examiners()]
        combined_list.append(combined_item)

    logger.debug("%s: visited the External Examiner Modules Index for package %s", request.user, package, extra={'form': form})
    template = loader.get_template('loads/modules/index.html')
    context = {
        'form': form,
        'external': external,
        'combined_list': combined_list,
        'package': package,
        'show_people': show_people,
    }
    return HttpResponse(template.render(context, request))


@login_required
def modules_details(request, module_id):
    """Detailed information on a given module"""
    # Get the module itself
    module = get_object_or_404(Module, pk=module_id)

    # Fetch the staff user associated with the person requesting
    try:
        staff = Staff.objects.get(user=request.user)

        if staff.is_external:
            if not staff.can_examine_module(module):
                return HttpResponseRedirect(reverse('forbidden'))
        else:
            if not staff.user.is_superuser and not module.package in staff.get_all_packages(include_hidden=True):
                return HttpResponseRedirect(reverse('forbidden'))
    except Staff.DoesNotExist:
        staff = None

    # Get all associated activities and allocations
    activities = Activity.objects.all().filter(module=module).order_by('name')
    modulestaff = ModuleStaff.objects.all().filter(module=module)

    total_contact_proportion = 0
    total_admin_proportion = 0
    total_assessment_proportion = 0
    for allocation in modulestaff:
        total_contact_proportion += allocation.contact_proportion
        total_admin_proportion += allocation.admin_proportion
        total_assessment_proportion += allocation.assessment_proportion

    # Get all the sign offs and assessment history
    # There's a subtle bug in using just the history for help, so using signoffs too.
    assessment_history = module.get_assessment_history()
    # Get all signoffs to date
    assessment_signoffs = AssessmentStateSignOff.objects.all().filter(module=module).order_by('-created')

    # Detect if any assessment resources exist that are not signed
    unsigned_items = False
    # Check the most recent tuple of signoffs and items exists
    if assessment_history and assessment_history[0]:
        # If it does, get the signoff
        (signoff, items) = assessment_history[0]
        # If the signoff is None, it means the items are not signed
        if signoff is None:
            #there are unsigned items
            unsigned_items = True

    logger.debug("%s: examined the Module Details for %s", request.user, module, extra={'form': form})
    template = loader.get_template('loads/modules/details.html')
    context = {
        'module': module,
        'moderators': module.moderators.all(),
        'total_hours': module.get_all_hours(),
        'contact_hours': module.get_contact_hours(),
        'admin_hours': module.get_admin_hours(),
        'assessment_hours': module.get_assessment_hours(),
        'modulestaff': modulestaff,
        'activities': activities,
        'assessment_history': assessment_history,
        'assessment_signoffs': assessment_signoffs,
        'package': module.package,
        'total_contact_proportion': total_contact_proportion,
        'total_admin_proportion': total_admin_proportion,
        'total_assessment_proportion': total_assessment_proportion,
        'unsigned_items': unsigned_items,
    }
    return HttpResponse(template.render(context, request))


@login_required
def add_assessment_sign_off(request, module_id):
    """Detailed information on a given module"""
    # Get the module itself
    module = get_object_or_404(Module, pk=module_id)

    # TODO: this is none too elegant, and could be outsourced
    # Fetch the staff user associated with the person requesting
    try:
        staff = Staff.objects.get(user=request.user)
        package = staff.package
    except Staff.DoesNotExist:
        staff = None

    # If neither here, time to boot
    if not staff:
        return HttpResponseRedirect(reverse('forbidden'))

    # Get all signoffs to date
    assessment_signoffs = AssessmentStateSignOff.objects.all().filter(module=module).order_by('-created')

    # Have we any already?
    if not len(assessment_signoffs):
        # No, so get all allowed initial states
        next_states = AssessmentState.objects.all().filter(initial_state=True)
    else:
        # There, are, so it's just the last object's sign off
        next_states = assessment_signoffs[0].assessment_state.next_states.all()

    # These are the possible successor states, but same may not be allowed to the current user
    for state in next_states:
        if not state.can_be_set_by(staff, module):
            next_states = next_states.exclude(pk=state.pk)

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = AssessmentStateSignOffForm(request.POST)

        # check whether it's valid:
        if form.is_valid():
            signoff = form.save(commit=False)
            signoff.signed_by = request.user
            signoff.module = module

            signoff.save()
            logger.info("%s: signed off assessment states for Module %s Index for package %s", request.user, module, package,
                         extra={'form': form})

            url = reverse('modules_details', kwargs={'module_id': module_id})
            return HttpResponseRedirect(url)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = AssessmentStateSignOffForm()
        form.fields['assessment_state'].queryset = next_states

    template = loader.get_template('loads/modules/add_assessment_signoff.html')
    context = {
        'package': package,
        'module': module,
        'assessment_signoffs': assessment_signoffs,
        'next_states': next_states,
        'form': form
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
@permission_required('loads.add_modulestaff')
@permission_required('loads.change_modulestaff')
@permission_required('loads.delete_modulestaff')
def staff_module_allocation(request, staff_id, package_id):
    """Edit the allocation of modules to a staff member"""

    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)
    # And the staff member we are going to act on
    staff = get_object_or_404(Staff, pk=staff_id)
    # And the package we are going to act on
    package = get_object_or_404(WorkPackage, pk=package_id)

    # If either the logged in user or target user aren't in the package, this is forbidden
    if package not in user_staff.get_all_packages() or package not in staff.get_all_packages(include_hidden=True):
        return HttpResponseRedirect(reverse('forbidden'))

    # Get a formset with only the choosable fields
    AllocationFormSet = modelformset_factory(ModuleStaff, formset=BaseModuleStaffByStaffFormSet,
                                             fields=('module', 'contact_proportion', 'admin_proportion',
                                                     'assessment_proportion'),
                                             can_delete=True)

    if request.method == "POST":
        formset = AllocationFormSet(
            request.POST, request.FILES,
            queryset=ModuleStaff.objects.filter(package=package).filter(staff=staff)
        )
        # We need to tweak the queryset to only allow modules in the package
        for form in formset:
            form.fields['module'].queryset = Module.objects.filter(package=package)
        if formset.is_valid():
            formset.save(commit=False)
            for form in formset:
                # Some fields are missing, so don't do a full save yet
                allocation = form.save(commit=False)
                # Fix the fields
                allocation.staff = staff
                allocation.package = package
            # Now do a real save
            formset.save(commit=True)
            logger.info("%s: edited the module allocation for %s on package %s", request.user, staff, package,
                         extra={'form': form})

            # redirect to the activites page
            # TODO this might just be a different package from this one, note.

            url = reverse('activities', args=[staff_id])
            return HttpResponseRedirect(url)
    else:
        formset = AllocationFormSet(queryset=ModuleStaff.objects.filter(package=package).filter(staff=staff))
        # Again, only allow modules in the package
        for form in formset:
            form.fields['module'].queryset = Module.objects.filter(package=package)

    return render(request, 'loads/staff/allocations.html', {'staff': staff, 'package': package, 'formset': formset})


@login_required
@staff_only
def generators_index(request):
    """Obtains a list of all ActivityGenerators in the User's selected WorkPackage"""

    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)
    # And the staff member we are going to act on
    staff = get_object_or_404(Staff, user=request.user)

    generators = ActivityGenerator.objects.all().filter(package=staff.package)

    logger.debug("%s: visited the Generators Index for workpackage %s", request.user, staff.package)
    template = loader.get_template('loads/generators/index.html')
    context = {
        'generators': generators,
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
@permission_required('loads.add_activity')
def generators_generate_activities(request, generator_id):
    """(Re)generate all activities for a given Activity Generator"""

    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And the generator
    generator = get_object_or_404(ActivityGenerator, pk=generator_id)

    # If either the logged in user or target user aren't in the package, this is forbidden
    if generator.package not in staff.get_all_packages(include_hidden="True"):
        return HttpResponseRedirect(reverse('forbidden'))

    generator.generate_activities()
    messages.success(request, 'Activities Regenerated.')
    logger.info("%s: triggered a Generator %s in Package %s", request.user, generator, generator.package)
    url = reverse('generators_index')
    return HttpResponseRedirect(url)


@login_required
@staff_only
@admin_only
def projects_index(request):
    """Obtains a list of all non archived projects"""
    # Fetch the tasks assigned against the specific user of the staff member
    staff = get_object_or_404(Staff, user=request.user)
    projects = Project.objects.all()

    logger.debug("%s: visited the Projects Index", request.user)
    template = loader.get_template('loads/projects/index.html')
    context = {
        'projects': projects,
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
@admin_only
@permission_required('loads.change_project')
@permission_required('loads.add_projectstaff')
@permission_required('loads.change_projectstaff')
@permission_required('loads.delete_projectstaff')
def projects_details(request, project_id):
    """Allows a Project and allocated staff to be edited"""

    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)

    # And the project we are going to act on
    project = get_object_or_404(Project, pk=project_id)
    package = user_staff.package

    # Get a formset with only the choosable fields
    ProjectStaffFormSet = modelformset_factory(ProjectStaff,  # formset=BaseModuleStaffByStaffFormSet,
                                               fields=('staff', 'start', 'end', 'hours_per_week'),
                                               can_delete=True)

    if request.method == "POST":
        project_form = ProjectForm(request.POST, instance=project)
        formset = ProjectStaffFormSet(
            request.POST, request.FILES,
            queryset=ProjectStaff.objects.filter(project=project),
        )
        if project_form.is_valid():
            project_form.save()

        if formset.is_valid():
            formset.save(commit=False)
            for form in formset:
                # Some fields are missing, so don't do a full save yet
                allocation = form.save(commit=False)
                # Fix the fields
                allocation.project = project
            # Now do a real save
            formset.save(commit=True)
            logger.info("%s: edited the details for Project %s", request.user, project,
                         extra={'form': form})

            # redirect to the activites page
            # TODO this might just be a different package from this one, note.

            url = reverse('projects_index')
            return HttpResponseRedirect(url)
    else:
        project_form = ProjectForm(instance=project)
        formset = ProjectStaffFormSet(queryset=ProjectStaff.objects.filter(project=project))
        for form in formset:
            form.fields['staff'].queryset = package.get_all_staff()

    return render(request, 'loads/projects/allocations.html',
                  {'project': project, 'project_form': project_form, 'formset': formset})


@login_required
@staff_only
@admin_only
@permission_required('loads.add_projectstaff')
@permission_required('loads.change_projectstaff')
@permission_required('loads.delete_projectstaff')
def projects_generate_activities(request, project_id):
    """(Re)generate all activities for a project"""

    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)

    # And the project we are going to act on
    project = get_object_or_404(Project, pk=project_id)

    project.generate_activities()
    messages.success(request, 'Activities Regenerated.')
    url = reverse('projects_index')
    return HttpResponseRedirect(url)


@login_required()
def workpackage_change(request):
    """Allows a user to change their current active workpackage"""
    # TODO: Needs to allow External Examiners.
    # Get the member of staff for the logged in user
    staff = get_object_or_404(Staff, user=request.user)

    # Get all workpackages that touch on the staff member's group
    packages = staff.get_all_packages()

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request and the given staff
        form = StaffWorkPackageForm(request.POST, instance=staff)
        form.fields['package'].queryset = packages
        # check whether it's valid:
        if form.is_valid():
            form.save()
            logger.info("%s: changed workpakage to %s", request.user, staff.package,
                         extra={'form': form})

            # Try to find where we came from
            next = request.POST.get('next', '/')
            if next:
                return HttpResponseRedirect(next)
            else:
                # redirect to the loads page
                url = reverse('loads')
                return HttpResponseRedirect(url)

    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = StaffWorkPackageForm(instance=staff)
        form.fields['package'].queryset = packages

    return render(request, 'loads/workpackage.html', {'form': form, 'staff': staff})


@login_required
@staff_only
@admin_only
@user_passes_test(lambda u: u.is_superuser)
def workpackage_migrate(request):
    """Allows a user to change their current active workpackage"""
    # Get the member of staff for the logged in user
    staff = get_object_or_404(Staff, user=request.user)

    # Get all workpackages that touch on the staff member's group
    packages = staff.get_all_packages()

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request and the given staff
        form = MigrateWorkPackageForm(request.POST)
        form.fields['source_package'].queryset = packages
        form.fields['destination_package'].queryset = packages

        # check whether it's valid:
        if form.is_valid():
            options = {
                'copy_programmes': form.cleaned_data['copy_programmes'],
                'copy_modules': form.cleaned_data['copy_modules'],
                'copy_modulestaff': form.cleaned_data['copy_modulestaff'],
                'copy_activities_generated': form.cleaned_data['copy_activities_generated'],
                'copy_activities_custom': form.cleaned_data['copy_activities_custom'],
                'copy_activities_modules': form.cleaned_data['copy_activities_modules'],
                'generate_projects': form.cleaned_data['generate_projects'], }

            destination_package = form.cleaned_data['destination_package']
            source_package = form.cleaned_data['source_package']
            logger.info("%s: migrated Package %s to %s", request.user, source_package, destination_package,
                         extra={'form': form})
            changes = destination_package.clone_from(source_package, options)

            template = loader.get_template('loads/workpackages/migrate_results.html')
            context = {
                'source_package': source_package,
                'destination_package': destination_package,
                'options': options,
                'changes': changes,
            }
            return HttpResponse(template.render(context, request))

    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = MigrateWorkPackageForm()
        form.fields['source_package'].queryset = packages
        form.fields['destination_package'].queryset = packages

    return render(request, 'loads/workpackages/migrate.html', {'form': form, 'staff': staff})


# Class based views

class CreateTaskView(PermissionRequiredMixin, CreateView):
    """View for creating a task"""
    permission_required = 'loads.add_task'
    model = Task
    success_url = reverse_lazy('tasks_index')
    fields = ['name', 'category', 'details', 'deadline', 'archive', 'targets', 'groups']

    def get_form(self, form_class=None):
        """We need to restrict form querysets"""
        form = super(CreateTaskView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        # Get all the groups this person might use, by aggregating them from packages.
        packages = staff.get_all_packages()
        groups = Group.objects.all().filter(workpackage__in=packages).distinct()

        form.fields['targets'].queryset = package_staff
        form.fields['groups'].queryset = groups
        return form


class UpdateTaskView(PermissionRequiredMixin, UpdateView):
    """View for creating a task"""
    permission_required = 'loads.change_task'
    model = Task
    success_url = reverse_lazy('tasks_index')
    fields = ['name', 'category', 'details', 'deadline', 'archive', 'targets', 'groups']

    def get_form(self, form_class=None):
        """We need to restrict form querysets"""
        form = super(UpdateTaskView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        # Get all the groups this person might use, by aggregating them from packages.
        packages = staff.get_all_packages()
        groups = Group.objects.all().filter(workpackage__in=packages).distinct()

        form.fields['targets'].queryset = package_staff
        form.fields['groups'].queryset = groups
        return form

    # @method_decorator(permission_required('loads.change_task', raise_exception=True))
    # def dispatch(self, request):
    #    return super(UpdateTaskView, self).dispatch(request)


class CreateModuleView(PermissionRequiredMixin, CreateView):
    """View for creating a Module"""
    permission_required = 'loads.add_module'
    model = Module
    fields = ['module_code', 'module_name', 'campus', 'size', 'semester', 'contact_hours', 'admin_hours',
              'assessment_hours',
              'coordinator', 'moderators', 'programmes', 'lead_programme']

    def get_form(self, form_class=None):
        """We need to restrict form querysets"""
        form = super(CreateModuleView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        # Work out the programmes in the package
        package_programmes = Programme.objects.all().filter(package=package)

        # And restrict the querysets as appropriate
        form.fields['coordinator'].queryset = package_staff
        form.fields['moderators'].queryset = package_staff
        form.fields['programmes'].queryset = package_programmes
        form.fields['lead_programme'].queryset = package_programmes
        return form

    def form_valid(self, form):
        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package

        self.object = form.save(commit=False)
        self.object.package = package
        response = super(CreateModuleView, self).form_valid(form)
        return response

    def get_success_url(self):
        """Send us back to the details view"""
        return reverse('modules_details', kwargs={'module_id': self.object.pk})


class UpdateModuleView(PermissionRequiredMixin, UpdateView):
    """View for editing a Module"""
    permission_required = 'loads.change_module'
    model = Module
    fields = ['module_code', 'module_name', 'campus', 'size', 'semester', 'contact_hours', 'admin_hours',
              'assessment_hours',
              'coordinator', 'moderators', 'programmes', 'lead_programme']

    def get_form(self, form_class=None):
        """We need to restrict form querysets"""
        form = super(UpdateModuleView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        # Work out the programmes in the package
        package_programmes = Programme.objects.all().filter(package=package)

        # And restrict the querysets as appropriate
        form.fields['coordinator'].queryset = package_staff
        form.fields['moderators'].queryset = package_staff
        form.fields['programmes'].queryset = package_programmes
        form.fields['lead_programme'].queryset = package_programmes
        return form

    def get_success_url(self):
        """Send us back to the details view"""
        return reverse('modules_details', kwargs={'module_id': self.object.pk})


class CreateProgrammeView(PermissionRequiredMixin, CreateView):
    """View for creating a Programme"""
    permission_required = 'loads.add_programme'
    model = Programme
    success_url = reverse_lazy('programmes_index')
    fields = ['programme_code', 'programme_name', 'examiners', 'directors']

    def get_form(self, form_class=None):
        form = super(CreateProgrammeView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        form.fields['directors'].queryset = package_staff
        return form

    def form_valid(self, form):
        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package

        self.object = form.save(commit=False)
        self.object.package = package
        response = super(CreateProgrammeView, self).form_valid(form)
        return response


class UpdateProgrammeView(PermissionRequiredMixin, UpdateView):
    """View for editing a Programme"""
    permission_required = 'loads.change_programme'
    model = Programme
    success_url = reverse_lazy('programmes_index')
    fields = ['programme_code', 'programme_name', 'examiners', 'directors']

    def get_form(self, form_class=None):
        form = super(UpdateProgrammeView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        form.fields["directors"].queryset = package_staff
        return form


class ProgrammeList(LoginRequiredMixin, ListView):

    """Generic view for Programme List"""
    model = Programme
    context_object_name = 'programmes'

    def get_queryset(self):
        try:
            staff = Staff.objects.get(user=self.request.user)
            package = staff.package
        except Staff.DoesNotExist:
            raise PermissionDenied("""Your user has no matching staff object.
            This is likely to be because no account has been created for you.""")
        else:
            return Programme.objects.all().filter(package=package)

@method_decorator(staff_only, name='dispatch')
class ActivityListView(LoginRequiredMixin, ListView):
    """Generic view for the Activities List"""
    model = Activity
    context_object_name = 'activities'

    def get_queryset(self):
        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package

        return Activity.objects.all().filter(package=package).order_by("staff", "name")


class CreateActivityView(PermissionRequiredMixin, CreateView):
    """View for creating an Activity"""
    permission_required = 'loads.add_activity'
    model = Activity
    success_url = reverse_lazy('activities_index')
    fields = ['name', 'hours', 'percentage', 'hours_percentage',
              'semester', 'activity_type', 'module', 'staff', 'comment']

    def get_form(self, form_class=None):
        form = super(CreateActivityView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        form.fields['staff'].queryset = package_staff
        form.fields['module'].queryset = Module.objects.all().filter(package=package)
        return form

    def form_valid(self, form):
        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package

        self.object = form.save(commit=False)
        self.object.package = package
        response = super(CreateActivityView, self).form_valid(form)
        return response


class UpdateActivityView(PermissionRequiredMixin, UpdateView):
    """View for updating an Activity"""
    permission_required = 'loads.change_activity'
    model = Activity
    success_url = reverse_lazy('activities_index')
    fields = ['name', 'hours', 'percentage', 'hours_percentage',
              'semester', 'activity_type', 'module', 'staff', 'comment']

    def get_form(self, form_class=None):
        form = super(UpdateActivityView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        form.fields['staff'].queryset = package_staff
        form.fields['module'].queryset = Module.objects.all().filter(package=package)
        return form

    def form_valid(self, form):
        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package

        self.object = form.save(commit=False)
        self.object.package = package
        response = super(UpdateActivityView, self).form_valid(form)
        return response

