from django.contrib import admin

# Importing some extra stuff to allow us to extend User

from django.contrib.auth.admin import UserAdmin
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


class ActivitySetAdmin(admin.ModelAdmin):
    list_display = ('name', 'created')
    list_filter = ('generator', 'project')


class ActivityGeneratorAdmin(admin.ModelAdmin):
    # list_display = ('name', 'created')
    list_filter = ('package', 'activity_type')


class AssessmentResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'module', 'owner', 'created')
    list_filter = ('module__package__name',)


class AssessmentStaffAdmin(admin.ModelAdmin):
    list_display = ('package', 'staff')
    list_filter = ('package', 'staff')


class AssessmentStateSignOffAdmin(admin.ModelAdmin):
    list_display = ('module', 'signed_by', 'assessment_state', 'created')
    list_filter = ('module__package__name',)


class CampusAdmin(admin.ModelAdmin):
    list_display = ('name', 'system_name')


class FacultyAdmin(admin.ModelAdmin):
    list_display = ('name', 'system_name')


class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'system_name', 'faculty')
    list_filter = ('faculty',)


class ModuleAdmin(admin.ModelAdmin):
    list_display = ('package', 'module_code', 'module_name', 'semester')
    list_filter = ('package', 'semester')


class ProgrammeAdmin(admin.ModelAdmin):
    list_filter = ('package',)


class StaffAdmin(admin.ModelAdmin):
    list_display = ('title', 'first_name', 'last_name', 'staff_number', 'fte', 'total_hours')
    list_display_links = ('first_name', 'last_name', 'staff_number')
    list_filter = ('package', 'is_external', 'has_workload','faculty','school')


class TaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'deadline')
    list_filter = ('archive', 'category')


class TaskCompletionAdmin(admin.ModelAdmin):
    list_display = ('task', 'staff', 'when', 'comment')


class ModuleStaffAdmin(admin.ModelAdmin):
    list_display = ('package', 'module', 'staff', 'contact_proportion', 'admin_proportion', 'assessment_proportion')
    list_filter = ('package__name',)


class WorkPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'startdate', 'enddate', 'draft', 'archive')


# Define an inline admin descriptor for Staff model
# which acts a bit like a singleton
class StaffInline(admin.StackedInline):
    model = Staff
    can_delete = False
    verbose_name_plural = 'staff'


admin.site.register(Activity, ActivityAdmin)
admin.site.register(ActivityGenerator, ActivityGeneratorAdmin)
admin.site.register(ActivitySet, ActivitySetAdmin)
admin.site.register(ActivityType)
admin.site.register(AssessmentResource, AssessmentResourceAdmin)
admin.site.register(AssessmentResourceType)
admin.site.register(AssessmentState)
admin.site.register(AssessmentStateSignOff, AssessmentStateSignOffAdmin)
admin.site.register(AssessmentStaff, AssessmentStaffAdmin)
admin.site.register(Body)
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
# See https://docs.djangoproject.com/en/1.8/topics/auth/customizing/#extending-user
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
