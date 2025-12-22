"""WAM URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  re_path(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  re_path(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  re_path(r'^blog/', include(blog_urls))
"""
from django.urls import include, path, re_path
from django.contrib import admin
from django.contrib.auth import views as auth_views

from WAM.settings import WAM_ADFS_AUTH, DEBUG_TOOLBAR

if DEBUG_TOOLBAR:
    from debug_toolbar.toolbar import debug_toolbar_urls

from loads import views

from loads.views import CreateProgrammeView
from loads.views import ProgrammeList
from loads.views import UpdateProgrammeView
from loads.views import DetailsProgrammeView
from loads.views import CreateModuleView
from loads.views import UpdateModuleView
from loads.views import CreateTaskView
from loads.views import UpdateTaskView
from loads.views import ActivityListView
from loads.views import CreateActivityView
from loads.views import UpdateActivityView

from WAM.settings import WAM_ADMIN_CONTACT_NAME, WAM_ADMIN_CONTACT_EMAIL

help_contact = {
    'help_name': WAM_ADMIN_CONTACT_NAME,
    'help_url': "mailto:" + WAM_ADMIN_CONTACT_EMAIL,
}

urlpatterns = [
    re_path(r'^$', views.index, name='index'),
    re_path(r'^accounts/login/$', auth_views.LoginView.as_view(extra_context=help_contact), name='login'),
    re_path(r'^accounts/logout/$', auth_views.LogoutView.as_view(), name='logout'),
    re_path(r'^accounts/external_logout/$', auth_views.LogoutView.as_view(next_page=views.external_logged_out), name='external_logout'),
    re_path(r'^workpackage/change/$', views.workpackage_change, name='workpackage_change'),
    re_path(r'^workpackage/migrate/$', views.workpackage_migrate, name='workpackage_migrate'),    
    re_path(r'^loads/$', views.loads, name='loads'),
    re_path(r'^loads_charts/$', views.loads_by_staff_chart, name='loads_charts'),
    re_path(r'^loads/modules/(?P<semesters>[0-9,]*)$', views.loads_modules, name='loads_modules'),
    re_path(r'^activities/(?P<staff_id>[0-9]+)$', views.activities, name='activities'),
    re_path(r'^activities/index/$', ActivityListView.as_view(), name='activities_index'),
    re_path(r'^activities/create/$', CreateActivityView.as_view(), name='create activity'),
    re_path(r'^activities/update/(?P<pk>[0-9]+)$', UpdateActivityView.as_view(), name='update activity'),
    re_path(r'^external/$', views.external_index, name='external_index'),
    re_path(r'^external/modules/index/(?P<semesters>[0-9,]*)$', views.external_modules_index,
            name='external_modules_index'),
    re_path(r'^generators/index/$', views.generators_index,
            name='generators_index'),
    re_path(r'^generators/generate_activities/(?P<generator_id>[0-9]+)$', views.generators_generate_activities,
            name='generators_generate_activities'),
    re_path(r'^tasks/index/$', views.tasks_index,
            name='tasks_index'),
    re_path(r'^tasks/archived/index/$', views.archived_tasks_index,
            name='archived_tasks_index'),
    re_path(r'^tasks/create/$', CreateTaskView.as_view(),
            name='create task'),
    re_path(r'^tasks/update/(?P<pk>[0-9]+)$', UpdateTaskView.as_view(),
            name='update task'),
    re_path(r'^tasks/completion/(?P<task_id>[0-9]+)/(?P<staff_id>[0-9]+)$', views.tasks_completion,
            name='tasks_completion'),
    re_path(r'^tasks/detail/(?P<task_id>[0-9]+)$', views.tasks_details, name='tasks_details'),
    re_path(r'^tasks/bystaff/(?P<staff_id>[0-9]+)$', views.tasks_bystaff, name='tasks_bystaff'),
    re_path(r'^modules/index/(?P<semesters>[0-9,]*)$', views.modules_index, name='modules_index'),
    re_path(r'^modules/details/(?P<module_id>[0-9]+)$', views.modules_details, name='modules_details'),
    re_path(r'^modules/add_assessment_resource/(?P<module_id>[0-9]+)$', views.add_assessment_resource,
            name='add_assessment_resource'),
    re_path(r'^modules/download_assessment_resource/(?P<resource_id>[0-9]+)$', views.download_assessment_resource,
            name='download_assessment_resource'),
    re_path(r'^modules/delete_assessment_resource/(?P<resource_id>[0-9]+)(?P<confirm>/confirm)?$',
            views.delete_assessment_resource, name='delete_assessment_resource'),
    re_path(r'^modules/add_assessment_sign_off/(?P<module_id>[0-9]+)$', views.add_assessment_sign_off,
            name='add_assessment_sign_off'),
    re_path(r'^modules/delete_assessment_sign_off/(?P<signoff_id>[0-9]+)(?P<confirm>/confirm)?$', views.delete_assessment_sign_off,
            name='delete_assessment_sign_off'),
    re_path(r'^modules/allocations/(?P<package_id>[0-9]+)/(?P<module_id>[0-9]+)$', views.module_staff_allocation,
            name='module_staff_allocation'),
    re_path(r'^modules/create/$', CreateModuleView.as_view(), name='create module'),
    re_path(r'^modules/update/(?P<pk>[0-9]+)$', UpdateModuleView.as_view(), name='update module'),
    re_path(r'^programmes/index/$', ProgrammeList.as_view(), name='programmes_index'),
    re_path(r'^programmes/create/$', CreateProgrammeView.as_view(), name='create programme'),
    re_path(r'^programmes/update/(?P<pk>[0-9]+)$', UpdateProgrammeView.as_view(), name='update programme'),
    re_path(r'^programmes/details/(?P<pk>[0-9]+)$', DetailsProgrammeView.as_view(), name='view programme'),
    re_path(r'^projects/index/$', views.projects_index, name='projects_index'),
    re_path(r'^projects/detail/(?P<project_id>[0-9]+)$', views.projects_details, name='projects_details'),
    re_path(r'^projects/generate_activities/(?P<project_id>[0-9]+)$', views.projects_generate_activities,
            name='projects_generate_activities'),
    re_path(r'^staff/allocation/(?P<package_id>[0-9]+)/(?P<staff_id>[0-9]+)$', views.staff_module_allocation,
            name='staff_module_allocation'),
    re_path(r'^forbidden/$', views.forbidden, name='forbidden'),
    re_path(r'^logged_out/$', views.logged_out, name='logged out'),
    re_path(r'^external_logged_out/$', views.external_logged_out, name='external logged out'),
    re_path(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^cadmin/$', views.custom_admin_index, name='custom_admin_index'),
    re_path(r'^cadmin/create_staff_user', views.create_staff_user, name='create staff user'),
    re_path(r'^cadmin/create_external_examiner', views.create_external_examiner, name='create external examiner'),
    re_path(r'^cadmin/assessment_staff/index/$', views.assessmentstaff_index, name='assessmentstaff_index'),
    re_path(r'^cadmin/assessment_staff/delete/(?P<assessmentstaff_id>[0-9]+)$', views.assessmentstaff_delete,
            name='assessmentstaff_delete'),

]


# Add ADFS login URLS if required
if WAM_ADFS_AUTH:
    urlpatterns.append(path('oauth2/', include('django_auth_adfs.urls')))

# Add Debug Toolbar
if DEBUG_TOOLBAR:
    urlpatterns += debug_toolbar_urls()

