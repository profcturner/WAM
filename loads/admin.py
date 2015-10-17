from django.contrib import admin

# Register your models here.

from django.contrib import admin

from .models import Activity
from .models import ActivityType
from .models import Module
from .models import Staff
from .models import StaffActivity

# Some code to augment the admin views in some cases

class ModuleAdmin(admin.ModelAdmin):
    list_display = ('module_code', 'module_name', 'semester')
    
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('name', 'module_details', 'hours', 'semester', 'activity_type', 'is_allocated')
    
class StaffAdmin(admin.ModelAdmin):
    list_display = ('title','first_name','last_name','staff_number','fte')
    
class StaffActivityAdmin(admin.ModelAdmin):
    list_display = ('staff_id', 'activity_id')


admin.site.register(ActivityType)
admin.site.register(Activity, ActivityAdmin)
admin.site.register(Module, ModuleAdmin)
admin.site.register(Staff, StaffAdmin)
admin.site.register(StaffActivity, StaffActivityAdmin)
