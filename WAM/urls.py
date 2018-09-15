"""WAM URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf.urls import include, url
from django.contrib import admin

from loads import views

from loads.views import CreateProgrammeView
from loads.views import ProgrammeList
from loads.views import UpdateProgrammeView
from loads.views import CreateModuleView
from loads.views import UpdateModuleView
from loads.views import CreateTaskView
from loads.views import UpdateTaskView
from loads.views import ActivityListView
from loads.views import CreateActivityView
from loads.views import UpdateActivityView

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^workpackage/change/$', views.workpackage_change, name='workpackage_change'),
    url(r'^workpackage/migrate/$', views.workpackage_migrate, name='workpackage_migrate'),    
    url(r'^loads/$', views.loads, name='loads'),
    url(r'^loads/modules/(?P<semesters>[0-9,]*)$', views.loads_modules, name='loads_modules'),
    url(r'^activities/(?P<staff_id>[0-9]+)$', views.activities, name='activities'),
    url(r'^activities/index/$', ActivityListView.as_view(), name='activities_index'),
    url(r'^activities/create/$', CreateActivityView.as_view(), name='create activity'),
    url(r'^activities/update/(?P<pk>[0-9]+)$$', UpdateActivityView.as_view(), name='update activity'),
    url(r'^external/modules/index/$', views.external_modules_index, name='external_modules_index'),
    url(r'^generators/index/$', views.generators_index, name='generators_index'),
    url(r'^generators/generate_activities/(?P<generator_id>[0-9]+)$', views.generators_generate_activities, name='generators_generate_activities'),
    url(r'^tasks/index/$', views.tasks_index, name='tasks_index'),
    url(r'^tasks/create/$', CreateTaskView.as_view(), name='create task'),
    url(r'^tasks/update/(?P<pk>[0-9]+)$', UpdateTaskView.as_view(), name='update task'),
    url(r'^tasks/completion/(?P<task_id>[0-9]+)/(?P<staff_id>[0-9]+)$', views.tasks_completion, name='tasks_completion'),    
    url(r'^tasks/detail/(?P<task_id>[0-9]+)$', views.tasks_details, name='tasks_details'),
    url(r'^tasks/bystaff/(?P<staff_id>[0-9]+)$', views.tasks_bystaff, name='tasks_bystaff'),
    url(r'^modules/index/(?P<semesters>[0-9,]*)$', views.modules_index, name='modules_index'),
    url(r'^modules/details/(?P<module_id>[0-9]+)$', views.modules_details, name='modules_details'),
    url(r'^modules/add_assessment_resource/(?P<module_id>[0-9]+)$', views.add_assessment_resource, name='add_assessment_resource'),
    url(r'^modules/download_assessment_resource/(?P<resource_id>[0-9]+)$', views.download_assessment_resource, name='download_assessment_resource'),
    url(r'^modules/delete_assessment_resource/(?P<resource_id>[0-9]+)$', views.delete_assessment_resource,
        name='delete_assessment_resource'),
    url(r'^modules/add_assessment_sign_off/(?P<module_id>[0-9]+)$', views.add_assessment_sign_off,
        name='add_assessment_sign_off'),
    url(r'^modules/examtracker/(?P<module_id>[0-9]+)$', views.exam_track_progress, name='exam_track_progress'),
    url(r'^modules/courseworktracker/(?P<module_id>[0-9]+)$', views.coursework_track_progress, name='coursework_track_progress'),
    url(r'^modules/allocations/(?P<package_id>[0-9]+)/(?P<module_id>[0-9]+)$', views.module_staff_allocation, name='module_staff_allocation'),
    url(r'^modules/create/$', CreateModuleView.as_view(), name='create module'),
    url(r'^modules/update/(?P<pk>[0-9]+)$', UpdateModuleView.as_view(), name='update module'),
    url(r'^programmes/index/$', ProgrammeList.as_view(), name='programmes_index'),
    url(r'^programmes/create/$', CreateProgrammeView.as_view(), name='create programme'),
    url(r'^programmes/update/(?P<pk>[0-9]+)$', UpdateProgrammeView.as_view(), name='update programme'),
    url(r'^projects/index/$', views.projects_index, name='projects_index'),
    url(r'^projects/detail/(?P<project_id>[0-9]+)$', views.projects_details, name='projects_details'),
    url(r'^projects/generate_activities/(?P<project_id>[0-9]+)$', views.projects_generate_activities, name='projects_generate_activities'),
    url(r'^staff/allocation/(?P<package_id>[0-9]+)/(?P<staff_id>[0-9]+)$', views.staff_module_allocation, name='staff_module_allocation'),    
    url(r'^forbidden/$', views.forbidden, name='forbidden'),
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^cadmin/$', views.custom_admin_index, name='custom_admin_index'),
    url(r'^cadmin/create_staff_user', views.create_staff_user, name='create staff user'),
    url(r'^cadmin/create_external_examiner', views.create_external_examiner, name='create external examiner'),

]
