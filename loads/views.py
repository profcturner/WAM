from django.shortcuts import get_object_or_404, render
from django.core.urlresolvers import reverse


# Create your views here.


from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader

from .models import Staff
from .models import Task
from .models import Activity
from .models import TaskCompletion
from .models import Module
from .models import ExamTracker
from .models import CourseworkTracker

from .forms import TaskCompletionForm

from django.contrib.auth.models import User, Group

def index(request):
    '''Main index page for non admin views'''
 
    template = loader.get_template('loads/index.html')
    context = RequestContext(request, {
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
    staff_list = Staff.objects.all().order_by('user__last_name')
    combined_list = []
    total = 0
    
    for staff in staff_list:
        load_info = staff.hours_by_semester()
        combined_item = [staff, load_info[0], load_info[1], load_info[2], load_info[3]]
        combined_list.append(combined_item)
        total += load_info[3]
        
    average = total / len(combined_list)
        
    template = loader.get_template('loads/loads.html')
    context = RequestContext(request, {
        'combined_list': combined_list,
        'total_total': total,
        'average': average,
    })
    return HttpResponse(template.render(context))
    
    
def activities(request, staff_id):
    '''Show the activities for a given staff member'''
    staff = get_object_or_404(Staff, pk=staff_id)
    activities = Activity.objects.all().filter(staff=staff).order_by('name')
    combined_list = []
    total = 0
        
    for activity in activities:
        load_info = activity.hours_by_semester()
        combined_item = [activity, load_info[0], load_info[1], load_info[2], load_info[3]]
        combined_list.append(combined_item)
        total += load_info[3]
            
    template = loader.get_template('loads/activities.html')
    context = RequestContext(request, {
        'staff': staff,
        'combined_list': combined_list,
        'total': total
    })
    return HttpResponse(template.render(context))


def tasks_index(request):
    '''Obtains a list of all non archived tasks'''
    # Fetch the tasks assigned against the specific user of the staff member
    tasks = Task.objects.all().exclude(archive=True).order_by('deadline')
                    
    template = loader.get_template('loads/tasks/index.html')
    context = RequestContext(request, {
        'tasks': tasks,
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
            combined_item = [task, False]
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
            
                            
    template = loader.get_template('loads/tasks/details.html')
    context = RequestContext(request, {
        'task': task,
        'combined_list_complete': combined_list_complete,
        'combined_list_incomplete' : combined_list_incomplete,
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
    if is_current_user and not can_override:
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

    return render(request, 'loads/tasks/completion.html', {'form': form, 'task': task, 'staff': staff})
    
    
def modules_index(request):
    """Shows a high level list of modules"""
    # Fetch the tasks assigned against the specific user of the staff member
    modules = Module.objects.all().order_by('module_code')
    
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
    })
    return HttpResponse(template.render(context))
    

def modules_details(request, module_id):
    """Detailed information on a given module"""
    # Get the module itself
    module = get_object_or_404(Module, pk=module_id)
    
    # Get all associated activities, exam and coursework trackers
    activities = Activity.objects.all().filter(module=module).order_by('name')
    exam_trackers = ExamTracker.objects.all().filter(module=module).order_by('created')
    coursework_trackers = CourseworkTracker.objects.all().filter(module=module).order_by('created')
    
    template = loader.get_template('loads/modules/details.html')
    context = RequestContext(request, {
        'module': module,
        'activities': activities,
        'exam_trackers': exam_trackers,
        'coursework_trackers': coursework_trackers,
    })
    return HttpResponse(template.render(context))
    
            