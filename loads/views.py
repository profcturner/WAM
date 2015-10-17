from django.shortcuts import render

# Create your views here.


from django.http import HttpResponse
from django.template import RequestContext, loader

from .models import Staff
from .models import Task
from .models import Activity

def index(request):
    staff_list = Staff.objects.all()
    load_info = []
    for staff in staff_list:
        load_info.append(staff.hours_by_semester())
        
    template = loader.get_template('loads/index.html')
    context = RequestContext(request, {
        'staff_list': staff_list,
        'load_info' : load_info,
    })
    return HttpResponse(template.render(context))
    

    