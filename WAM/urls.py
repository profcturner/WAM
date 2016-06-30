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

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^workpackage/change/$', views.workpackage_change, name='workpackage_change'),
    url(r'^workpackage/migrate/$', views.workpackage_migrate, name='workpackage_migrate'),    
    url(r'^loads/$', views.loads, name='loads'),
    url(r'^loads/modules/$', views.loads_modules, name='loads_modules'),
    url(r'^activities/(?P<staff_id>[0-9]+)$', views.activities, name='activities'),
    url(r'^tasks/index/$', views.tasks_index, name='tasks_index'),
    url(r'^tasks/completion/(?P<task_id>[0-9]+)/(?P<staff_id>[0-9]+)$', views.tasks_completion, name='tasks_completion'),    
    url(r'^tasks/detail/(?P<task_id>[0-9]+)$', views.tasks_details, name='tasks_details'),
    url(r'^tasks/bystaff/(?P<staff_id>[0-9]+)$', views.tasks_bystaff, name='tasks_bystaff'),
    url(r'^modules/index/$', views.modules_index, name='modules_index'),
    url(r'^modules/details/(?P<module_id>[0-9]+)$', views.modules_details, name='modules_details'),
    url(r'^modules/examtracker/(?P<module_id>[0-9]+)$', views.exam_track_progress, name='exam_track_progress'),
    url(r'^modules/courseworktracker/(?P<module_id>[0-9]+)$', views.coursework_track_progress, name='coursework_track_progress'),
    url(r'^modules/allocations/(?P<package_id>[0-9]+)/(?P<module_id>[0-9]+)$', views.module_staff_allocation, name='module_staff_allocation'),
    url(r'^projects/index/$', views.projects_index, name='projects_index'),
    url(r'^projects/detail/(?P<project_id>[0-9]+)$', views.projects_details, name='projects_details'),
    url(r'^projects/generate_activities/(?P<project_id>[0-9]+)$', views.projects_generate_activities, name='projects_generate_activities'),
    url(r'^staff/allocation/(?P<package_id>[0-9]+)/(?P<staff_id>[0-9]+)$', views.staff_module_allocation, name='staff_module_allocation'),    
    url(r'^forbidden/$', views.forbidden, name='forbidden'),
    url(r'^admin/', include(admin.site.urls)),
]
