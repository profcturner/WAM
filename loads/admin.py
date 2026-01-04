from django.contrib import admin

# Importing some extra stuff to allow us to extend User

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

# Register your models here.

# Import given models

from .models import Activity
from .models import ActivitySet
from .models import ActivityType
from .models import ActivityGenerator
from .models import AssessmentResource
from .models import AssessmentResourceType
from .models import AssessmentState
from .models import AssessmentStateSignOff
from .models import AssessmentStaff
from .models import Body
from .models import Campus
from .models import Category
from .models import Faculty
from .models import Module
from .models import ModuleSize
from .models import ModuleStaff
from .models import Programme
from .models import Project
from .models import ProjectStaff
from .models import School
from .models import Staff
from .models import Task
from .models import TaskCompletion
from .models import Resource
from .models import WorkPackage

# Some code to augment the admin views in some cases


class ActivityAdmin(admin.ModelAdmin):
    list_display = ('package', 'name', 'module', 'staff', 'hours', 'percentage', 'semester', 'activity_type',
                    'is_allocated')
    list_filter = ('package', 'module', 'staff')
    search_fields = ['module__module_code', 'module__module_name', 'name', 'staff__user__last_name', 'staff__user__first_name']


class ActivitySetAdmin(admin.ModelAdmin):
    list_display = ('name', 'created')
    list_filter = ('generator', 'project')
    search_fields = ['name', 'generator__name', 'project__name']


class ActivityGeneratorAdmin(admin.ModelAdmin):
    list_display = ('name', 'package')
    list_filter = ('package', 'activity_type')
    search_fields = ['name']


class AssessmentResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'module', 'owner', 'created')
    list_filter = ('module__package__name',)
    search_fields = ['name', 'module__module_name', 'module__module_code']


class AssessmentStaffAdmin(admin.ModelAdmin):
    list_display = ('package', 'staff')
    list_filter = ('package', 'staff')
    search_fields = ['staff__user__last_name', 'staff__user__first_name']


class AssessmentStateSignOffAdmin(admin.ModelAdmin):
    list_display = ('module', 'signed_by', 'assessment_state', 'created')
    list_filter = ('module__package__name',)
    search_fields = ['module__module_code', 'module__module_name', 'signed_by__first_name', 'signed_by__last_name', 'signed_by__username']


class BodyAdmin(admin.ModelAdmin):
    search_fields = ['name']


class CampusAdmin(admin.ModelAdmin):
    list_display = ('name', 'system_name')


class FacultyAdmin(admin.ModelAdmin):
    list_display = ('name', 'system_name')


class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'system_name', 'faculty')
    list_filter = ('faculty',)
    search_fields = ['name', 'system_name', 'faculty__name', 'faculty__system_name']


class ModuleAdmin(admin.ModelAdmin):
    list_display = ('package', 'module_code', 'module_name', 'semester')
    list_filter = ('package', 'semester')
    search_fields = ['module_code','module_name']


class ProgrammeAdmin(admin.ModelAdmin):
    list_filter = ('package',)
    search_fields = ['programme_code', 'programme_name']


class StaffAdmin(admin.ModelAdmin):
    list_display = ('title', 'first_name', 'last_name', 'staff_number', 'fte', 'has_workload', 'is_external')
    list_display_links = ('first_name', 'last_name', 'staff_number')
    list_filter = ('faculty', 'school', 'is_external', 'has_workload', 'package')
    search_fields = ['staff_number', 'user__first_name', 'user__last_name']


class TaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'deadline')
    list_filter = ('archive', 'category')
    search_fields = ['name']


class TaskCompletionAdmin(admin.ModelAdmin):
    list_display = ('task', 'staff', 'when', 'comment')
    search_fields = ['task__name', 'staff__user__first_name', 'staff__user__last_name']


class ModuleStaffAdmin(admin.ModelAdmin):
    list_display = ('package', 'module', 'staff', 'contact_proportion', 'admin_proportion', 'assessment_proportion')
    list_filter = ('package__name',)
    search_fields = ['module__module_code', 'module__module_name', 'staff__user__last_name', 'staff__user__first_name']


class WorkPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'startdate', 'enddate', 'draft', 'archive')
    search_fields = ['name']


# Define an inline admin descriptor for Staff model
# which acts a bit like a singleton
class StaffInline(admin.StackedInline):
    model = Staff
    can_delete = False
    verbose_name_plural = 'staff'


# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = [StaffInline]


admin.site.register(Activity, ActivityAdmin)
admin.site.register(ActivityGenerator, ActivityGeneratorAdmin)
admin.site.register(ActivitySet, ActivitySetAdmin)
admin.site.register(ActivityType)
admin.site.register(AssessmentResource, AssessmentResourceAdmin)
admin.site.register(AssessmentResourceType)
admin.site.register(AssessmentState)
admin.site.register(AssessmentStateSignOff, AssessmentStateSignOffAdmin)
admin.site.register(AssessmentStaff, AssessmentStaffAdmin)
admin.site.register(Body, BodyAdmin)
admin.site.register(Campus, CampusAdmin)
admin.site.register(Category)
admin.site.register(Faculty, FacultyAdmin)
admin.site.register(Module, ModuleAdmin)
admin.site.register(ModuleStaff, ModuleStaffAdmin)
admin.site.register(ModuleSize)
admin.site.register(Programme, ProgrammeAdmin)
admin.site.register(Project)
admin.site.register(ProjectStaff)
admin.site.register(School, SchoolAdmin)
admin.site.register(Staff, StaffAdmin)
admin.site.register(Task, TaskAdmin)
admin.site.register(TaskCompletion, TaskCompletionAdmin)
admin.site.register(Resource)
admin.site.register(WorkPackage, WorkPackageAdmin)

# Re-register UserAdmin
# See https://docs.djangoproject.com/en/6.0/topics/auth/customizing/#extending-user
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
