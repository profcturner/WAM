from django.shortcuts import get_object_or_404, render
from django.core.urlresolvers import reverse


# Create your views here.


from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader

from .models import ACADEMIC_YEAR

from .models import Staff
from .models import Task
from .models import Activity
from .models import TaskCompletion
from .models import Module
from .models import ModuleStaff
from .models import ExamTracker
from .models import CourseworkTracker
from .models import WorkPackage

from .forms import TaskCompletionForm
from .forms import ExamTrackerForm
from .forms import CourseworkTrackerForm
from .forms import StaffWorkPackageForm

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
    

def loads(request):
    '''Show the loads for all members of staff'''

    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package
    
    # We will group the data according to groups in the package
    group_data = []
    
    #for group in staff.package.groups:
    #    staff_list = Staff.objects.all().filter(user__in=group).order_by('user__last_name')

    
    #TODO We should create a staff list only featuring those in groups related to the package
    staff_list = Staff.objects.all().order_by('user__last_name')
    combined_list = []
    total = 0
    
    for staff in staff_list:
        load_info = staff.hours_by_semester(package=package)
        combined_item = [staff, load_info[0], load_info[1], load_info[2], load_info[3], 100*load_info[0]/staff.fte]
        combined_list.append(combined_item)
        total += load_info[0]
    
    if len(combined_list):    
        average = total / len(combined_list)
    else:
        average = 0
        
    template = loader.get_template('loads/loads.html')
    context = RequestContext(request, {
        'combined_list': combined_list,
        'total_total': total,
        'average': average,
        'package': package,
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
        
        combined_item = [str(moduledata.module) + ' Contact Hours',
            semester1_c_hours, semester2_c_hours, semester3_c_hours, c_hours_proportion]
        combined_list_modules.append(combined_item)
        combined_item = [str(moduledata.module) + ' Admin Hours',
            semester1_ad_hours, semester2_ad_hours, semester3_ad_hours, ad_hours_proportion]
        combined_list_modules.append(combined_item)
        combined_item = [str(moduledata.module) + ' Assessment Hours',
            semester1_as_hours, semester2_as_hours, semester3_as_hours, as_hours_proportion]
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
    tasks = Task.objects.all().exclude(archive=True).order_by('deadline')
    
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

    
def modules_index(request):
    """Shows a high level list of modules"""
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package
    
    modules = Module.objects.all().filter(package=package).order_by('module_code')
    
    combined_list = []
    for module in modules:
        # get the most recent exam tracker and coursework tracker
        exam_trackers = ExamTracker.objects.all().filter(module=module).order_by('-created')[:1]
        coursework_trackers = CourseworkTracker.objects.all().filter(module=module).order_by('-created')[:1]
        
        if len(exam_trackers) > 0:
            exam_tracker = exam_trackers[0]
        else:
            exam_tracker = False

        if len(coursework_trackers) > 0:
            coursework_tracker = coursework_trackers[0]
        else:
            coursework_tracker = False

        combined_item = [module, exam_tracker, coursework_tracker]
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
    exam_trackers = ExamTracker.objects.all().filter(module=module).order_by('created')
    coursework_trackers = CourseworkTracker.objects.all().filter(module=module).order_by('created')
    
    template = loader.get_template('loads/modules/details.html')
    context = RequestContext(request, {
        'module': module,
        'activities': activities,
        'exam_trackers': exam_trackers,
        'coursework_trackers': coursework_trackers,
        'package': package,
    })
    return HttpResponse(template.render(context))
    
    
def workpackage_change(request):
    """Allows a user to change their current active workpackage"""
    # Get the member of staff for the logged in user
    staff = get_object_or_404(Staff, user=request.user)
    
    # Get all workpackages that touch on the staff member's group
    packages = WorkPackage.objects.all().distinct()
    
    #target_by_groups = User.objects.all().filter(groups__in=target_groups).distinct().order_by('last_name')
    #all_targets = task.get_all_targets()
    
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request and the given staff
        form = StaffWorkPackageForm(request.POST, instance = staff)
        # check whether it's valid:
        if form.is_valid():
            form.save()
            
            # redirect to the loads page
            url = reverse('loads')
            return HttpResponseRedirect(url)

    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = StaffWorkPackageForm(instance = staff)

    return render(request, 'loads/workpackage.html', {'form': form, 'staff': staff})

        