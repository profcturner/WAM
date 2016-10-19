import os
import mimetypes

from django.shortcuts import get_object_or_404, render
from django.core.urlresolvers import reverse
from django.forms import modelformset_factory
from django.contrib import messages

# Create your views here.

from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader

from .models import ACADEMIC_YEAR

from .models import ActivityGenerator
from .models import AssessmentResource
from .models import Staff
from .models import Task
from .models import Activity
from .models import TaskCompletion
from .models import Module
from .models import ModuleStaff
from .models import Programme
from .models import ExamTracker
from .models import CourseworkTracker
from .models import Project
from .models import ProjectStaff
from .models import WorkPackage

from .forms import AssessmentResourceForm
from .forms import LoadsByModulesForm
from .forms import TaskCompletionForm
from .forms import ExamTrackerForm
from .forms import CourseworkTrackerForm
from .forms import StaffWorkPackageForm
from .forms import MigrateWorkPackageForm
from .forms import ProjectForm
from .forms import BaseModuleStaffByModuleFormSet
from .forms import BaseModuleStaffByStaffFormSet


from django.contrib.auth.models import User, Group

def index(request):
    '''Main index page for non admin views'''
 
    template = loader.get_template('loads/index.html')
    context = RequestContext(request, {
        'home_page': True,
    })
    return HttpResponse(template.render(context))


def forbidden(request):
    '''General permissions failure warning'''
 
    template = loader.get_template('loads/forbidden.html')
    context = RequestContext(request, {
    })
    return HttpResponse(template.render(context))
    

def download_assessment_resource(request, resource_id):
    """Download an assessment resource"""
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And the resource object
    resource = get_object_or_404(AssessmentResource, pk=resource_id)
    # And the moderators
    moderators = resource.module.moderators.all()
    
    # Assume a lack of permissions
    permission = False
    
    # The owner can download
    if not permission:
        if staff == resource.owner:
            permission = True
        
    # A moderator can download
    if not permission:
        for moderator in moderators:
            if staff == moderator:
                permission = True 
    
    # External Examiners can download if they are the lead
    if not permission:
        if resource.module.lead_programme:
            examiners = resource.module.lead_programme.examiners.all()
            for examiner in examiners:
                if staff == examiner:
                    permission = True
      
    if not permission:
        return HttpResponseRedirect('/forbidden/')
    
    resource.downloads += 1
    resource.save()
    
    # Get the base filename, and try and work out the type
    filename = os.path.basename(resource.resource.name)
    file_mimetype = mimetypes.guess_type(filename)
    
    # Start a response
    response = HttpResponse(resource.resource.file, content_type=file_mimetype)

    # Let's suggest the filename
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    response['X-Sendfile'] = filename
    #response['Content-Length'] = os.stat(settings.MEDIA_ROOT + os.sep + resource.resource.name).st_size 
    return response


def loads(request):
    '''Show the loads for all members of staff'''

    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    
    package = staff.package

    # If either the workpackage for the member of staff is undefined
    # or it's set to a package they are not "in" send them to the chooser
    if not package or package not in staff.get_all_packages():
        url = reverse('workpackage_change')
        return HttpResponseRedirect(url)
        
    total = 0.0
    total_staff = 0
    group_data = []
 
    # Go through each group in turn
    for group in staff.package.groups.all():
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
            # Check any staff member with no load is active, if not, skip them
            if not staff.is_active() and load_info[0] == 0:
                continue
            combined_item = [staff, load_info[0], load_info[1], load_info[2], load_info[3], 100*load_info[0]/staff.fte]
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
        group_data.append([group, group_list, group_total, group_average, group_allocated_staff, group_allocated_average])
        total += group_total
        total_staff += len(staff_list)
    
    if total_staff:    
        average = total / total_staff
    else:
        average = 0
        
    template = loader.get_template('loads/loads.html')
    context = RequestContext(request, {
        'group_data' : group_data,
        'total': total,
        'average': average,
        'package': package,
        'loads_menu': True,
    })
    return HttpResponse(template.render(context))
    
    
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
        brief_details=False


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
    
    template = loader.get_template('loads/loads/modules.html')
    context = RequestContext(request, {
        'form': form,
        'brief_details': brief_details,
        'valid_semesters': valid_semesters,
        'combined_list': combined_list,
        'package': package,
        'loads_menu': True,
        'staff_details' : staff_details,
    })
    return HttpResponse(template.render(context))


def activities(request, staff_id):
    '''Show the activities for a given staff member'''
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package
    
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
        
        combined_item = [str(moduledata.module) + ' Contact Hours', c_hours_proportion,
            semester1_c_hours, semester2_c_hours, semester3_c_hours]
        combined_list_modules.append(combined_item)
        combined_item = [str(moduledata.module) + ' Admin Hours', ad_hours_proportion,
            semester1_ad_hours, semester2_ad_hours, semester3_ad_hours]
        combined_list_modules.append(combined_item)
        combined_item = [str(moduledata.module) + ' Assessment Hours', as_hours_proportion,
            semester1_as_hours, semester2_as_hours, semester3_as_hours]
        combined_list_modules.append(combined_item)
        
        semester1_total += (semester1_c_hours + semester1_ad_hours + semester1_as_hours)
        semester2_total += (semester2_c_hours + semester2_ad_hours + semester2_as_hours)
        semester3_total += (semester3_c_hours + semester3_ad_hours + semester3_as_hours)
        
        total += c_hours_proportion + as_hours_proportion + ad_hours_proportion
        
    template = loader.get_template('loads/activities.html')
    context = RequestContext(request, {
        'staff': staff,
        'combined_list': combined_list,
        'combined_list_modules': combined_list_modules,
        'semester1_total': semester1_total,
        'semester2_total': semester2_total,
        'semester3_total': semester3_total,
        'total': total,
        'package': package,
    })
    return HttpResponse(template.render(context))


def tasks_index(request):
    '''Obtains a list of all non archived tasks'''
    # Fetch the tasks assigned against the specific user of the staff member
    staff = get_object_or_404(Staff, user=request.user)
    tasks = staff.get_all_tasks()
    #tasks = Task.objects.all().exclude(archive=True).order_by('deadline')
    
    augmented_tasks = []
    for task in tasks:
        augmented_tasks.append([task, task.is_urgent(), task.is_overdue()])
                    
    template = loader.get_template('loads/tasks/index.html')
    context = RequestContext(request, {
        'augmented_tasks': augmented_tasks,
    })
    return HttpResponse(template.render(context))
            

def tasks_bystaff(request, staff_id):
    '''Show the tasks assigned against the specific user of the staff member'''
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
            
            
    template = loader.get_template('loads/tasks/bystaff.html')
    context = RequestContext(request, {
        'staff': staff,
        'combined_list_complete': combined_list_complete,
        'combined_list_incomplete': combined_list_incomplete,
    })
    return HttpResponse(template.render(context))

    
def tasks_details(request, task_id):
    '''Obtains a list of all completions for a given task'''
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
            
                            
    template = loader.get_template('loads/tasks/details.html')
    context = RequestContext(request, {
        'task': task,
        'overdue': task.is_overdue(),
        'urgent': task.is_urgent(),
        'combined_list_complete': combined_list_complete,
        'combined_list_incomplete' : combined_list_incomplete,
        'percentage_complete' : percentage_complete
    })
    return HttpResponse(template.render(context))
    
    
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
        return HttpResponseRedirect('/forbidden/')
    
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
            
            # redirect to the task details
            # TODO: which is a pain if we came from the bystaff view
            url = reverse('tasks_details', kwargs={'task_id': task_id})
            return HttpResponseRedirect(url)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = TaskCompletionForm()

    return render(request, 'loads/tasks/completion.html', {'form': form, 'task': task, 
        'overdue': task.is_overdue(), 
        'urgent': task.is_urgent(),'staff': staff})


def add_assessment_resource(request, module_id):
    """Provide a form for uploading a module resource"""
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # Get the module itself
    module = get_object_or_404(Module, pk=module_id)

    # Check for a valid permission at this stage
    #can_override = request.user.has_perm('loads.add_assessment_resource')
    #if not can_override:
    #    return HttpResponseRedirect('/forbidden/')
    
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
            url = reverse('modules_details', kwargs={'module_id': module_id})
            return HttpResponseRedirect(url)


    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = AssessmentResourceForm()

    return render(request, 'loads/modules/add_assessment_resource.html', {'form': form, 'staff': staff, 'module':module})


def exam_track_progress(request, module_id):
    """Processes recording of an exam QA tracking event"""
    # Get the module itself
    module = get_object_or_404(Module, pk=module_id)

    # Check for a valid permission at this stage
    can_override = request.user.has_perm('loads.add_examtracker')
    if not can_override:
        return HttpResponseRedirect('/forbidden/')
    
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = ExamTrackerForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            
            new_item = form.save(commit=False)
            # TODO: More elegant handling of ACADEMIC_YEAR needed
            new_item.module = module
            new_item.academic_year = ACADEMIC_YEAR
            
            new_item.save()
            form.save_m2m()
            url = reverse('modules_details', kwargs={'module_id': module_id})
            return HttpResponseRedirect(url)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = ExamTrackerForm()

    return render(request, 'loads/modules/examtracker.html', {'form': form, 'module': module})
 
    
def coursework_track_progress(request, module_id):
    """Processes recording of a coursework QA tracking event"""
    # Get the module itself
    module = get_object_or_404(Module, pk=module_id)

    # Check for a valid permission at this stage
    can_override = request.user.has_perm('loads.add_courseworktracker')
    if not can_override:
        return HttpResponseRedirect('/forbidden/')
    
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = CourseworkTrackerForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            
            new_item = form.save(commit=False)
            # TODO: More elegant handling of ACADEMIC_YEAR needed
            new_item.module = module
            new_item.academic_year = ACADEMIC_YEAR
            
            new_item.save()
            form.save_m2m()
            url = reverse('modules_details', kwargs={'module_id': module_id})
            return HttpResponseRedirect(url)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = CourseworkTrackerForm()

    return render(request, 'loads/modules/courseworktracker.html', {'form': form, 'module': module})


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
        return HttpResponseRedirect('/forbidden/')
        
    # The logged in user should be able to do this via the Admin interface, or disallow.
    permission = request.user.has_perm('loads.add_modulestaff') and request.user.has_perm('loads.change_modulestaff') and request.user.has_perm('loads.delete_modulestaff')
        
    if not permission:
        return HttpResponseRedirect('/forbidden/')
    
    # Get a formset with only the choosable fields
    AllocationFormSet = modelformset_factory(ModuleStaff, formset=BaseModuleStaffByModuleFormSet,
        fields=('staff', 'contact_proportion', 'admin_proportion', 'assessment_proportion'),
        can_delete=True)
        
    if request.method == "POST":
        formset = AllocationFormSet(
            request.POST, request.FILES,
            queryset=ModuleStaff.objects.filter(package=package).filter(module=module).order_by('staff__user__last_name')
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
                   
            # redirect to the activites page
            #TODO this might just be a different package from this one, note.
        
            url = reverse('modules_details', args=[module_id])
            return HttpResponseRedirect(url)
    else:
        formset = AllocationFormSet(queryset=ModuleStaff.objects.filter(package=package).filter(module=module).order_by('staff__user__last_name'))
        # Again, only allow staff members in the package
        for form in formset:
            form.fields['staff'].queryset = package.get_all_staff()
        
    return render(request, 'loads/modules/allocations.html', {'module': module, 'package':package, 'formset': formset})


    
def modules_index(request):
    """Shows a high level list of modules"""
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package
    
    modules = Module.objects.all().filter(package=package).order_by('module_code')
    
    combined_list = []
    for module in modules:
        # get the most recent assessment resource
        resources = AssessmentResource.objects.all().filter(module=module).order_by('-created')[:1]
        
        if len(resources) > 0:
            resource = resources[0]
        else:
            resource = False

        combined_item = [module, resource]
        combined_list.append(combined_item)
    
    template = loader.get_template('loads/modules/index.html')
    context = RequestContext(request, {
        'combined_list': combined_list,
        'package': package,
    })
    return HttpResponse(template.render(context))


def modules_details(request, module_id):
    """Detailed information on a given module"""
    # Get the module itself
    module = get_object_or_404(Module, pk=module_id)
    
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package
    
    # Get all associated activities, exam and coursework trackers
    activities = Activity.objects.all().filter(module=module).filter(package=package).order_by('name')
    modulestaff = ModuleStaff.objects.all().filter(module=module).filter(package=package)
    assessment_resources = AssessmentResource.objects.all().filter(module=module).order_by('-created')
    exam_trackers = ExamTracker.objects.all().filter(module=module).order_by('created')
    coursework_trackers = CourseworkTracker.objects.all().filter(module=module).order_by('created')
    
    total_contact_proportion = 0
    total_admin_proportion = 0
    total_assessment_proportion = 0
    for allocation in modulestaff:
        total_contact_proportion += allocation.contact_proportion
        total_admin_proportion += allocation.admin_proportion
        total_assessment_proportion += allocation.assessment_proportion
        
    
    template = loader.get_template('loads/modules/details.html')
    context = RequestContext(request, {
        'module': module,
        'total_hours' : module.get_all_hours(),
        'contact_hours': module.get_contact_hours(),
        'admin_hours': module.get_admin_hours(),
        'assessment_hours': module.get_assessment_hours(),
        'modulestaff': modulestaff,
        'activities': activities,
        'assessment_resources': assessment_resources,
        'exam_trackers': exam_trackers,
        'coursework_trackers': coursework_trackers,
        'package': package,
        'total_contact_proportion': total_contact_proportion,
        'total_admin_proportion': total_admin_proportion,
        'total_assessment_proportion': total_assessment_proportion,
    })
    return HttpResponse(template.render(context))
    
    
def staff_module_allocation(request, staff_id, package_id):
    """Edit the allocation of modules to a staff member"""
    
    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)
    # And the staff member we are going to act on
    staff = get_object_or_404(Staff, pk=staff_id)
    # And the package we are going to act on
    package = get_object_or_404(WorkPackage, pk=package_id)
    
    # If either the logged in user or target user aren't in the package, this is forbidden
    if package not in user_staff.get_all_packages() or package not in staff.get_all_packages():
        return HttpResponseRedirect('/forbidden/')
        
    # The logged in user should be able to do this via the Admin interface, or disallow.
    permission = request.user.has_perm('loads.add_modulestaff') and request.user.has_perm('loads.change_modulestaff') and request.user.has_perm('loads.delete_modulestaff')
        
    if not permission:
        return HttpResponseRedirect('/forbidden/')
    
    # Get a formset with only the choosable fields
    AllocationFormSet = modelformset_factory(ModuleStaff, formset=BaseModuleStaffByStaffFormSet,
        fields=('module', 'contact_proportion', 'admin_proportion', 'assessment_proportion'),
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
                   
            # redirect to the activites page
            #TODO this might just be a different package from this one, note.
        
            url = reverse('activities', args=[staff_id])
            return HttpResponseRedirect(url)
    else:
        formset = AllocationFormSet(queryset=ModuleStaff.objects.filter(package=package).filter(staff=staff))
        # Again, only allow modules in the package
        for form in formset:
            form.fields['module'].queryset = Module.objects.filter(package=package)
        
    return render(request, 'loads/staff/allocations.html', {'staff': staff, 'package':package, 'formset': formset})


def generators_index(request):
    '''Obtains a list of all ActivityGenerators in the User's selected WorkPackage'''

    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)
    # And the staff member we are going to act on
    staff = get_object_or_404(Staff, user=request.user)

    generators = ActivityGenerator.objects.all().filter(package=staff.package)

    template = loader.get_template('loads/generators/index.html')
    context = RequestContext(request, {
        'generators': generators,
    })
    return HttpResponse(template.render(context))


def generators_generate_activities(request, generator_id):
    """(Re)generate all activities for a given Activity Generator"""
    
    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)
    staff = get_object_or_404(Staff, user=request.user)
    # And the generator
    generator = get_object_or_404(ActivityGenerator, pk=generator_id)
    
    # If either the logged in user or target user aren't in the package, this is forbidden
    if staff.package not in user_staff.get_all_packages() or not request.user.has_perm('loads.add_activity'):
        return HttpResponseRedirect('/forbidden/')

        
    generator.generate_activities()
    messages.success(request, 'Activities Regenerated.')
    url = reverse('generators_index')
    return HttpResponseRedirect(url)


def projects_index(request):
    '''Obtains a list of all non archived projects'''
    # Fetch the tasks assigned against the specific user of the staff member
    staff = get_object_or_404(Staff, user=request.user)
    projects = Project.objects.all()
    
                    
    template = loader.get_template('loads/projects/index.html')
    context = RequestContext(request, {
        'projects': projects,
    })
    return HttpResponse(template.render(context))


def projects_details(request, project_id):
    """Allows a Project and allocated staff to be edited"""
    
    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)

    # And the project we are going to act on
    project = get_object_or_404(Project, pk=project_id)
    package = user_staff.package

        
    # The logged in user should be able to do this via the Admin interface, or disallow changes (views ok)
    permission = request.user.has_perm('loads.change_project') and request.user.has_perm('loads.change_projectstaff') and request.user.has_perm('loads.delete_projectstaff') and request.user.has_perm('loads.add_projectstaff')

    
    # Get a formset with only the choosable fields
    ProjectStaffFormSet = modelformset_factory(ProjectStaff, #formset=BaseModuleStaffByStaffFormSet,
        fields=('staff', 'start', 'end', 'hours_per_week'),
        can_delete=True)
        
    if request.method == "POST":
        if not permission:
            return HttpResponseRedirect('/forbidden/')
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
                   
            # redirect to the activites page
            #TODO this might just be a different package from this one, note.
        
            url = reverse('projects_index')
            return HttpResponseRedirect(url)
    else:
        project_form = ProjectForm(instance=project)
        formset = ProjectStaffFormSet(queryset=ProjectStaff.objects.filter(project=project))
        for form in formset:
            form.fields['staff'].queryset = package.get_all_staff()
        # Again, only allow modules in the package
        #for form in formset:
         #   form.fields['module'].queryset = Module.objects.filter(package=package)
        
    return render(request, 'loads/projects/allocations.html', {'project':project, 'project_form':project_form, 'formset': formset})


def projects_generate_activities(request, project_id):
    """(Re)generate all activities for a project"""
    
    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)

    # And the project we are going to act on
    project = get_object_or_404(Project, pk=project_id)
    
    #TODO: Establish sensible permissions
    # If either the logged in user or target user aren't in the package, this is forbidden
    #if package not in user_staff.get_all_packages() or package not in staff.get_all_packages():
    #    return HttpResponseRedirect('/forbidden/')
        
    # The logged in user should be able to do this via the Admin interface, or disallow.
    permission = request.user.has_perm('loads.add_projectstaff') and request.user.has_perm('loads.change_projectstaff') and request.user.has_perm('loads.delete_projectstaff')
    if not permission:
        return HttpResponseRedirect('/forbidden/')
        
    project.generate_activities()
    messages.success(request, 'Activities Regenerated.')
    url = reverse('projects_index')
    return HttpResponseRedirect(url)
    


def workpackage_change(request):
    """Allows a user to change their current active workpackage"""
    # Get the member of staff for the logged in user
    staff = get_object_or_404(Staff, user=request.user)
    
    # Get all workpackages that touch on the staff member's group
    packages = staff.get_all_packages()
    
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request and the given staff
        form = StaffWorkPackageForm(request.POST, instance = staff)
        form.fields['package'].queryset = packages
        # check whether it's valid:
        if form.is_valid():
            form.save()
            
            # redirect to the loads page
            url = reverse('loads')
            return HttpResponseRedirect(url)

    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = StaffWorkPackageForm(instance = staff)
        form.fields['package'].queryset = packages

    return render(request, 'loads/workpackage.html', {'form': form, 'staff': staff})


def workpackage_migrate(request):
    """Allows a user to change their current active workpackage"""
    # Get the member of staff for the logged in user
    staff = get_object_or_404(Staff, user=request.user)
    
    # Check for a valid permission at this stage
    can_override = (request.user.has_perm('loads.add_activity')
        and request.user.has_perm('loads_add_module')
        and request.user.has_perm('loads_add_modulestaff'))
        
    if not can_override:
        return HttpResponseRedirect('/forbidden/')
        
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

            options = {'activities': form.cleaned_data['copy_activities'],
                'modules': form.cleaned_data['copy_modules'],
                'modulestaff': form.cleaned_data['copy_modulestaff'], }
            destination_package = form.cleaned_data['destination_package']
            source_package = form.cleaned_data['source_package']
            changes = destination_package.clone_from(source_package, options)
            
            template = loader.get_template('loads/workpackages/migrate_results.html')
            context = RequestContext(request, {
                'source_package': source_package,
                'destination_package': destination_package,
                'options': options,
                'changes': changes,
            })
            return HttpResponse(template.render(context))

    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = MigrateWorkPackageForm()
        form.fields['source_package'].queryset = packages
        form.fields['destination_package'].queryset = packages

    return render(request, 'loads/workpackages/migrate.html', {'form': form, 'staff': staff})

        