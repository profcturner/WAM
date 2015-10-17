from django.shortcuts import render

# Create your views here.


from django.http import HttpResponse
from django.template import RequestContext, loader

from .models import Staff
from .models import Task
from .models import Activity

def index(request):
    staff_list = Staff.objects.all()
    combined_list = []
    total = 0
    
    for staff in staff_list:
        load_info = staff.hours_by_semester()
        combined_item = [staff, load_info[0], load_info[1], load_info[2], load_info[3]]
        combined_list.append(combined_item)
        total += load_info[3]
        
    average = total / len(combined_list)
        
    template = loader.get_template('loads/index.html')
    context = RequestContext(request, {
        'combined_list': combined_list,
        'total_total': total,
        'average': average,
    })
    return HttpResponse(template.render(context))
    

    