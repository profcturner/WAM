from django.shortcuts import get_object_or_404, render
from django.core.urlresolvers import reverse


# Create your views here.


from django.http import HttpResponse
from django.template import RequestContext, loader

from .models import Staff
from .models import Task
from .models import Activity
from .models import TaskCompletion

from django.contrib.auth.models import User, Group

def index(request):
 
    template = loader.get_template('loads/index.html')
    context = RequestContext(request, {
    })
    return HttpResponse(template.render(context))
    

def loads(request):
    staff_list = Staff.objects.all()
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
    staff = get_object_or_404(Staff, pk=staff_id)
    activities = Activity.objects.all().filter(staff=staff)
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
    tasks = Task.objects.all().exclude(archive=True)
                    
    template = loader.get_template('loads/tasks/index.html')
    context = RequestContext(request, {
        'tasks': tasks,
    })
    return HttpResponse(template.render(context))
            

def tasks_bystaff(request, staff_id):
    '''Show the tasks assigned against the specific user of the staff member'''
    staff = get_object_or_404(Staff, pk=staff_id)
    user_tasks = Task.objects.all().filter(targets=staff).exclude(archive=True).distinct()
    
    # And those assigned against the group
    groups = Group.objects.all().filter(user=staff.user)
    group_tasks = Task.objects.all().filter(groups__in=groups).distinct()
    
    # Combine them
    all_tasks = user_tasks | group_tasks

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
    # Get the task itself
    task = get_object_or_404(Task, pk=task_id)
    
    # Get all Users implicated
    # These are staff objects
    target_by_users = task.targets.all()
    target_groups = task.groups.all()
    # These are user objects 
    target_by_groups = User.objects.all().filter(groups__in=target_groups).distinct()
    all_targets = []
    
    for staff in target_by_users:
        all_targets.append(staff)
    for user in target_by_groups:
        staff = Staff.objects.all().filter(user=user)[0]
        if not staff in all_targets:
            all_targets.append(staff)
    
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
            