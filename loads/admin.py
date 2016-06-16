from django.contrib import admin

# Importing some extra stuff to allow us to extend User

from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

# Register your models here.

# Import given models

from .models import Activity
from .models import ActivityType
from .models import Campus
from .models import Category
from .models import CourseworkTracker
from .models import ExamTracker
from .models import Module
from .models import ModuleSize
from .models import ModuleStaff
from .models import Staff
from .models import Task
from .models import TaskCompletion
from .models import Resource
from .models import WorkPackage

# Some code to augment the admin views in some cases

class ModuleAdmin(admin.ModelAdmin):
    list_display = ('package', 'module_code', 'module_name', 'semester')
    list_filter = ('package__name',)
    
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('package', 'name', 'module', 'staff', 'hours', 'percentage', 'semester', 'activity_type', 'is_allocated')
    list_filter = ('package__name',)
    
class StaffAdmin(admin.ModelAdmin):
    list_display = ('title','first_name','last_name','staff_number','fte','total_hours')
    
class TaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'deadline')
    
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

# Define a new User admin
class UserAdmin(UserAdmin):
    inlines = (StaffInline, )


admin.site.register(ActivityType)
admin.site.register(Activity, ActivityAdmin)
admin.site.register(Campus)
admin.site.register(Category)
admin.site.register(CourseworkTracker)
admin.site.register(ExamTracker)
admin.site.register(Module, ModuleAdmin)
admin.site.register(ModuleStaff, ModuleStaffAdmin)
admin.site.register(ModuleSize)
admin.site.register(Staff, StaffAdmin)
admin.site.register(Task, TaskAdmin)
admin.site.register(TaskCompletion, TaskCompletionAdmin)
admin.site.register(Resource)
admin.site.register(WorkPackage, WorkPackageAdmin)

# Re-register UserAdmin
# See https://docs.djangoproject.com/en/1.8/topics/auth/customizing/#extending-user
admin.site.unregister(User)
admin.site.register(User, UserAdmin)