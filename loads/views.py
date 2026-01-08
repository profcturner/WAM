import os
import mimetypes
import logging

from django.core.mail import mail_admins
from django.shortcuts import get_object_or_404, render
from django.http import Http404
from django.urls import reverse, reverse_lazy
from django.forms import modelformset_factory
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme

from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.core.exceptions import PermissionDenied

# Class Views
from django.views.generic import ListView, DetailView, CreateView, UpdateView

# Permission decorators
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from .decorators import staff_only, external_only, admin_only
from django.utils.decorators import method_decorator
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.contrib.auth.models import User, Group

from .models import ActivityGenerator, Category
from .models import AssessmentResource
from .models import AssessmentStaff
from .models import AssessmentState
from .models import AssessmentStateSignOff
from .models import Staff
from .models import Task
from .models import Activity
from .models import TaskCompletion
from .models import Module
from .models import ModuleStaff
from .models import Programme
from .models import Project
from .models import ProjectStaff
from .models import WorkPackage

from .forms import AssessmentResourceForm
from .forms import AssessmentStaffForm
from .forms import AssessmentStateSignOffForm
from .forms import LoadsByModulesForm
from .forms import TaskForm
from .forms import TaskCompletionForm
from .forms import StaffWorkPackageForm
from .forms import MigrateWorkPackageForm
from .forms import ModulesIndexForm
from .forms import ProjectForm
from .forms import StaffCreationForm
from .forms import ExternalExaminerCreationForm
from .forms import BaseModuleStaffByModuleFormSet
from .forms import BaseModuleStaffByStaffFormSet
from .forms import DateInput
from .forms import DateTimeInput

from WAM.settings import WAM_VERSION, WAM_ADMIN_CONTACT_EMAIL, WAM_ADMIN_CONTACT_NAME

# Get an instance of a logger
logger = logging.getLogger(__name__)


def next_page_push(request, url):
    """
    A helper function to push any next_page data into the session

    Doing this can avoid overzealous web application firewalls, hopefully

    :param request: The user's request data
    :param url:     The url to redirect to on next pop
    """
    logger.debug("[%s] pushing next page %s in session" % (request.user, url))
    request.session['next_page'] = url


def next_page_pop(request, backup_url=None):
    """
    A helper function to pop any next_page data from the session

    Doing this can avoid overzealous web application firewalls, hopefully

    :param request:     The user's request data
    :param backup_url:  Use this URL is the pop fails
    :return:            The url for redirection, or a backup if not found in the session
    """
    url = request.session.pop('next_page')
    # Just in case we can't get one
    if url is None:
        logger.debug("[%s] could not pop next page from session, bacup url used %s" % (request.user, url))
        return backup_url
    else:
        logger.debug("[%s] popping next page %s from session" % (request.user, url))
        return url

def index(request):
    """Main index page for non admin views"""

    template = loader.get_template('loads/index.html')
    context = {
        'home_page': True,
        'admin_name': WAM_ADMIN_CONTACT_NAME,
        'admin_email': WAM_ADMIN_CONTACT_EMAIL,
    }
    logger.info("[%s] visiting home page" % request.user)
    return HttpResponse(template.render(context, request))

def about(request):
    """
    About the application
    """

    template = loader.get_template('loads/about.html')
    context = {
        'home_page': True,
        'admin_name': WAM_ADMIN_CONTACT_NAME,
        'admin_email': WAM_ADMIN_CONTACT_EMAIL,
        'wam_version': WAM_VERSION,
    }
    logger.info("[%s] visiting about page" % request.user)
    return HttpResponse(template.render(context, request))


def external_index(request):
    """The main home page for External Examiners"""

    template = loader.get_template('loads/external/index.html')
    context = {
        'home_page': True,
        'admin_name': WAM_ADMIN_CONTACT_NAME,
        'admin_email': WAM_ADMIN_CONTACT_EMAIL,
    }
    logger.info("[%s] visiting external examiners home page" % request.user)
    return HttpResponse(template.render(context, request))


def forbidden(request):
    """General permissions failure warning"""

    template = loader.get_template('loads/forbidden.html')
    logger.info("[%s] action was forbidden" % request.user)

    return HttpResponse(template.render({}, request))


def logged_out(request):
    """Show that we are logged out"""

    template = loader.get_template('loads/logged_out.html')
    logger.info("staff member logged out")

    return HttpResponse(template.render({}, request))


def external_logged_out(request):
    """Show that an external examiner is logged out"""

    template = loader.get_template('loads/external/logged_out.html')
    logger.info("external examiner logged out")

    return HttpResponse(template.render({}, request))


@login_required
def download_assessment_resource(request, resource_id):
    """Download an assessment resource"""
    # Get the resource object
    resource = get_object_or_404(AssessmentResource, pk=resource_id)
    logger.info("[%s] attempting to download assessment resource %u" % (request.user, resource.id), extra={'resource': resource})

    # Fetch the staff user associated with the person requesting
    try:
        staff = Staff.objects.get(user=request.user)
    except Staff.DoesNotExist:
        staff = None

    if not staff:
        logger.info("[%s] forbidden from downloading resource, no staff object." % request.user)
        return HttpResponseRedirect(reverse('forbidden'))

    permission = resource.is_downloadable_by(staff)

    if not permission:
        logger.info("[%s] forbidden from downloading resource, no permission for this resource." % request.user)
        return HttpResponseRedirect(reverse('forbidden'))

    resource.downloads += 1
    resource.save()

    # Get the base filename, and try and work out the type
    filename = os.path.basename(resource.resource.name)
    file_mimetype = mimetypes.guess_type(filename)[0]

    # Start a response
    try:
        logger.info("[%s] downloading assessment resource %u" % (request.user, resource.id), extra={'resource': resource})
        response = HttpResponse(resource.resource.file, content_type=file_mimetype)
    except FileNotFoundError:
        logger.critical("File %s, missing for existing resource id %u" % (filename, resource.pk), extra={'resource': resource})
        mail_admins("WAM error, missing file", "File %s, missing for existing resource id %u" % (filename, resource.pk))
        raise Http404("The requested file was not found.")


    # Let's suggest the filename
    response['Content-Disposition'] = 'inline; filename="%s"' % filename
    response['Content-Length'] = len(resource.resource.file)
    return response


@login_required
def delete_assessment_resource(request, resource_id, confirm=None):
    """Delete an assessment resource, should not be possible for signed resources, except for superuser"""
    # Get the resource object
    resource = get_object_or_404(AssessmentResource, pk=resource_id)
    logger.info("[%s] attempting to delete assessment resource %u" % (request.user, resource.id),
                extra={'resource': resource})

    # TODO: this is none too elegant, and could be outsourced
    # Fetch the staff user associated with the person requesting
    try:
        staff = Staff.objects.get(user=request.user)
    except Staff.DoesNotExist:
        staff = None

    # If neither here, time to boot
    if not staff:
        logger.info("[%s] forbidden from deleting resource, no staff object." % request.user)
        return HttpResponseRedirect(reverse('forbidden'))

    # Assume a lack of permissions
    permission = False

    # If the resource is signed, deletions are forbidden except for superuser
    signed = len(AssessmentStateSignOff.objects.all().filter(module=resource.module). \
                 filter(created__gt=resource.created))

    if signed:
        if staff and staff.user.is_superuser:
            logger.debug("[%s] is a superuser, permission granted to delete this resource." % request.user)
            permission = True
    else:
        # Unsigned resources can be deleted, by owners and module coordinators
        if resource.owner == staff or resource.module.coordinator == staff:
            logger.debug("[%s] owns the resource or is a module coordinator, permission granted to delete this resource." % request.user)
            permission = True

    if not permission:
        logger.info("[%s] forbidden from deleting resource, no permission for this resource." % request.user)
        return HttpResponseRedirect(reverse('forbidden'))

    # Ok, we are allowed to delete
    # Check if the deletion is confirmed
    if not confirm:
        context = {
            'resource': resource
        }
        logger.info("[%s] initiating assessment resource %u deletion" % (request.user, resource.id),
                    extra={'resource': resource})
        template = loader.get_template('loads/modules/delete_assessment_resource.html')
        return HttpResponse(template.render(context, request))

    # If we are still here we can delete safely
    logger.info("[%s] confirming assessment resource %u deletion" % (request.user, resource.id), extra={'resource': resource})
    resource.delete()
    messages.info(request, 'Deleted assessment resource.')

    url = reverse('modules_details', kwargs={'module_id': resource.module_id})
    return HttpResponseRedirect(url)


@login_required
@staff_only
def loads(request):
    """Show the loads for all members of staff"""

    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package

    # If the staff member is a superuser just check the workpackage exists
    if staff.user.is_superuser:
        if not package:
            url = reverse('workpackage_change')
            return HttpResponseRedirect(url)
    else:
        # or it's set to a package they are not "in" send them to the chooser
        if not package or package not in staff.get_all_packages():
            #TODO: Probably really want to 403 this...
            url = reverse('workpackage_change')
            return HttpResponseRedirect(url)

    logger.info("[%s] loads by staff viewed" % request.user, extra={'package': package})
    # This controls whether hours or percentages are shown
    show_percentages = package.show_percentages

    # We shall want to consider totals for averages, but as some users can be in multiple
    # groups, we will keep a list to make sure we don't double count.
    total = 0.0
    total_staff = 0
    counted_staff = list()
    group_data = []

    # Go through each group in turn
    for group in package.groups.all():
        group_list = []
        group_size = 0
        group_total = 0.0
        group_average = 0.0
        group_allocated_staff = 0
        group_allocated_average = 0.0
        # Get the users in the group
        users = User.objects.all().filter(groups__in=[group]).distinct()
        # And the associated staff objects
        staff_list = Staff.objects.all().filter(user__in=users).order_by('user__last_name')
        for staff in staff_list:
            load_info = staff.hours_by_semester(package=package)
            # Note below: the reason for checking any load as will as conditions is to allow
            # colleagues to appear in other workpackages in times they had an allocated load, even
            # if they are now inactive or flagged as having no workload

            # Check any staff member with no load is active, if not, skip them
            if not staff.is_active() and load_info[0] == 0:
                continue
            # If this colleague isn't flagged as having a workload and doesn't have any, also skip
            if not staff.has_workload and load_info[0] ==0:
                continue

            # Check if we have seen this person already, but if not add them to the grand total
            if not staff in counted_staff:
                logger.debug("loads: considering staff %s, total hours %f" % (staff, load_info[0]))
                counted_staff.append(staff)
                counted_staff.append(staff)
                total += load_info[0]
                total_staff += 1

            # Ok, we should include this colleague
            if show_percentages:
                combined_item = [staff, 100 * load_info[0] / package.nominal_hours,
                                 100 * load_info[1] / package.nominal_hours,
                                 100 * load_info[2] / package.nominal_hours,
                                 100 * load_info[3] / package.nominal_hours,
                                 100 * (100 * load_info[0] / staff.fte) / package.nominal_hours]
            else:
                combined_item = [staff, load_info[0], load_info[1], load_info[2], load_info[3],
                                 100 * load_info[0] / staff.fte]
            group_list.append(combined_item)
            group_total += load_info[0]
            group_size += 1
            if load_info[0]:
                # Also count staff with allocated hours
                group_allocated_staff += 1
        if group_size:
            group_average = group_total / group_size
        if group_allocated_staff:
            group_allocated_average = group_total / group_allocated_staff
        group_data.append(
            [group, group_list, group_total, group_average, group_allocated_staff, group_allocated_average])

    if total_staff:
        average = total / total_staff
    else:
        average = 0

    template = loader.get_template('loads/loads.html')
    context = {
        'group_data': group_data,
        'total': total,
        'total_staff': total_staff,
        'average': average,
        'package': package,
        'show_percentages': show_percentages,
        'loads_menu': True,
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
def loads_by_staff_chart(request):
    """
    Show a graph of the loads for all members of staff in all groups in a given workpackage

    The principal focus of this view is allowing clear peer comparability. And as such FTE scaling is
    currently build in, and while there is a parameter to disable it, by default, staff are sorted in
    descending load order in each group.
    """
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package

    # If the staff member is a superuser just check the workpackage exists
    if staff.user.is_superuser:
        if not package:
            url = reverse('workpackage_change')
            return HttpResponseRedirect(url)
    else:
        # or it's set to a package they are not "in" send them to the chooser
        if not package or package not in staff.get_all_packages():
            #TODO: Probably really want to 403 this...
            url = reverse('workpackage_change')
            return HttpResponseRedirect(url)

    logger.info("[%s] loads by staff chart viewed" % request.user, extra={'package': package})
    # We will likely want these to be configurable
    # By default, we will sort lists by highest to lowest workload (if False, alphabetically)
    sort_lists = True
    # By default, we will add lines at 90% and 100%
    show_90_110 = False
    #TODO: This is still pretty much built in as True by assumption in some of the code below
    scale_fte = True

    # I'm not sure that it makes sense not to have percentages, but in case we change our minds
    show_percentages = True

    # We shall want to consider totals for averages, but as some users can be in multiple
    # groups, we will keep a list to make sure we don't double count.
    total = 0.0
    total_staff = 0
    counted_staff = list()
    group_data = []

    # Go through each group in turn
    for group in package.groups.all():
        # We are going to have some summary statistics for each group too
        group_list = []
        group_size = 0
        group_total = 0.0
        group_average = 0.0
        group_allocated_staff = 0
        group_allocated_average = 0.0
        # Get the users in the group, order by last name initially
        users = User.objects.all().filter(groups__in=[group]).distinct()
        # And the associated staff objects, sort them here to avoid a double hit
        staff_list = Staff.objects.all().filter(user__in=users).order_by('user__last_name')
        for staff in staff_list:
            staff_hours_by_category = staff.hours_by_category(package=package)

            # Total hours
            hours = sum(staff_hours_by_category.values())

            # Note below: the reason for checking any load as will as conditions is to allow
            # colleagues to appear in other workpackages in times when they had an allocated load, even
            # if they are now inactive or flagged as having no workload

            # Check any staff member with no load is active, if not, skip them
            if not staff.is_active() and hours == 0:
                continue
            # If this colleague isn't flagged as having a workload and doesn't have any, also skip
            if not staff.has_workload and hours ==0:
                continue

            # Check if we have seen this person already, but if not add them to the grand total
            if not staff in counted_staff:
                logger.debug("loads: considering staff %s, total hours %f" % (staff, hours))
                counted_staff.append(staff)
                total += hours
                total_staff += 1

            # For each member of staff, we want a list which includes, for each category
            # The category, the number of hours in that category, and the percentage for the category
            # as calculated against the nominal hours for the package
            staff_loads_by_category = list()
            for key, value in staff_hours_by_category.items():
                if scale_fte:
                    staff_loads_by_category.append(
                        [key, value, 100 * value / (package.nominal_hours * staff.fte / 100)])
                else:
                    staff_loads_by_category.append(
                        [key, value, 100 * value / package.nominal_hours])

            # For each staff member, the bar width is keyed to be 80% for 100% load, up to 100% for 125% load
            # This allows us to show some moderately overloaded staff clearly.
            if scale_fte:
                bar_width = 0.8 * 100 * (100 / staff.fte) * hours / package.nominal_hours
            else:
                bar_width = 0.8 * 100 * hours / package.nominal_hours

            if bar_width < 80:
                bar_width = 80
            if bar_width > 100:
                bar_width = 100

            # Now add all this data for each member of staff
            combined_item = [staff, staff_loads_by_category, hours, bar_width, hours * (100/staff.fte)]
            group_list.append(combined_item)
            group_total += hours
            group_size += 1
            if hours !=0:
                # Also count staff with allocated hours
                group_allocated_staff += 1
        if group_size:
            group_average = group_total / group_size
        if group_allocated_staff:
            group_allocated_average = group_total / group_allocated_staff

        # We want to sort with the most loaded staff at the top, using scaled hours to compensate for FTE
        if sort_lists:
            group_list = sorted(group_list, key=lambda item : item[4], reverse=True)

        group_data.append(
            [group, group_list, group_total, group_average, group_allocated_staff, group_allocated_average])

    if total_staff:
        average = total / total_staff
    else:
        average = 0

    template = loader.get_template('loads/loads_charts.html')
    context = {
        'sort_lists': sort_lists,
        'show_90_110': show_90_110,
        'group_data': group_data,
        'total': total,
        'total_staff': total_staff,
        'average': average,
        'package': package,
        'categories': Category.objects.all(),
        'show_percentages': show_percentages,
        'loads_menu': True,
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
def loads_modules(request, semesters, staff_details=False):
    """Shows allocation information by modules"""
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package

    logger.info("[%s] loads by modules viewed" % request.user, extra={'package': package})
    modules = Module.objects.all().filter(package=package).order_by('module_code')

    # if this is a POST request we need to process the form data
    brief_details = None
    if request.method == 'POST':
        # create a form instance and populate it with data from the request
        form = LoadsByModulesForm(request.POST)

        # check whether it's valid:
        if form.is_valid():
            semesters = form.cleaned_data['semesters']
            brief_details = form.cleaned_data['brief_details']

    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = LoadsByModulesForm()
        # If semesters came via get, let's populate the form
        form.fields['semesters'].initial = semesters
        brief_details = False

    # Check for any semester limitations, split by comma if something is actually there
    if semesters:
        valid_semesters = semesters.split(',')
    else:
        valid_semesters = list()

    combined_list = []
    for module in modules:
        # Is it valid for the semester, i.e. are any of its semesters in the one being passed in?
        if len(valid_semesters):
            module_semesters = module.semester.split(',')
            valid_semester = False
            for m_sem in module_semesters:
                for v_sem in valid_semesters:
                    if m_sem == v_sem:
                        valid_semester = True
            if not valid_semester:
                continue

        # Get Allocation information
        module_staff = ModuleStaff.objects.all().filter(module=module)
        contact_proportion = 0
        admin_proportion = 0
        assessment_proportion = 0
        extra_hours = 0
        for allocation in module_staff:
            contact_proportion += allocation.contact_proportion
            admin_proportion += allocation.admin_proportion
            assessment_proportion += allocation.assessment_proportion

        activities = Activity.objects.all().filter(module=module)
        for activity in activities:
            hours_per_semester = activity.hours_by_semester()
            extra_hours += hours_per_semester[0]

        module_info = [module,
                       module.get_contact_hours(),
                       contact_proportion,
                       module.get_admin_hours(),
                       admin_proportion,
                       module.get_assessment_hours(),
                       assessment_proportion,
                       extra_hours,
                       module_staff]

        combined_list.append(module_info)

    template = loader.get_template('loads/loads/modules.html')
    context = {
        'form': form,
        'brief_details': brief_details,
        'valid_semesters': valid_semesters,
        'combined_list': combined_list,
        'package': package,
        'loads_menu': True,
        'staff_details': staff_details,
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
def activities(request, staff_id):
    """Show the activities for a given staff member"""
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package

    show_percentages = package.show_percentages
    # Now the staff member we want to look at
    staff = get_object_or_404(Staff, pk=staff_id)

    logger.info("[%s] viewed activities for %s" % (request.user, staff), extra={'package': package})
    activities = Activity.objects.all().filter(staff=staff).filter(package=package).order_by('name')
    combined_list = []
    combined_list_modules = []
    total = 0.0
    semester1_total = 0.0
    semester2_total = 0.0
    semester3_total = 0.0

    for activity in activities:
        load_info = activity.hours_by_semester()
        if show_percentages:
            combined_item = [activity,
                             100 * load_info[0] / package.nominal_hours,
                             100 * load_info[1] / package.nominal_hours,
                             100 * load_info[2] / package.nominal_hours,
                             100 * load_info[3] / package.nominal_hours]
        else:
            combined_item = [activity, load_info[0], load_info[1], load_info[2], load_info[3]]
        combined_list.append(combined_item)
        semester1_total += load_info[1]
        semester2_total += load_info[2]
        semester3_total += load_info[3]
        total += load_info[0]

    # Add hours calculated from "automatic" module allocation
    modulestaff = ModuleStaff.objects.all().filter(staff=staff_id).filter(package=package)
    for moduledata in modulestaff:
        c_hours = moduledata.module.get_contact_hours_by_semester()
        as_hours = moduledata.module.get_assessment_hours_by_semester()
        ad_hours = moduledata.module.get_admin_hours_by_semester()

        semester1_c_hours = c_hours[1] * moduledata.contact_proportion / 100
        semester1_as_hours = as_hours[1] * moduledata.assessment_proportion / 100
        semester1_ad_hours = ad_hours[1] * moduledata.admin_proportion / 100

        semester2_c_hours = c_hours[2] * moduledata.contact_proportion / 100
        semester2_as_hours = as_hours[2] * moduledata.assessment_proportion / 100
        semester2_ad_hours = ad_hours[2] * moduledata.admin_proportion / 100

        semester3_c_hours = c_hours[3] * moduledata.contact_proportion / 100
        semester3_as_hours = as_hours[3] * moduledata.assessment_proportion / 100
        semester3_ad_hours = ad_hours[3] * moduledata.admin_proportion / 100

        c_hours_proportion = c_hours[0] * moduledata.contact_proportion / 100
        as_hours_proportion = as_hours[0] * moduledata.assessment_proportion / 100
        ad_hours_proportion = ad_hours[0] * moduledata.admin_proportion / 100

        if show_percentages:
            combined_item = [str(moduledata.module) + ' Contact Hours',
                             100 * c_hours_proportion / package.nominal_hours,
                             100 * semester1_c_hours / package.nominal_hours,
                             100 * semester2_c_hours / package.nominal_hours,
                             100 * semester3_c_hours / package.nominal_hours]
        else:
            combined_item = [str(moduledata.module) + ' Contact Hours', c_hours_proportion,
                             semester1_c_hours, semester2_c_hours, semester3_c_hours]
        combined_list_modules.append(combined_item)

        if show_percentages:
            combined_item = [str(moduledata.module) + ' Admin Hours',
                             100 * ad_hours_proportion / package.nominal_hours,
                             100 * semester1_ad_hours / package.nominal_hours,
                             100 * semester2_ad_hours / package.nominal_hours,
                             100 * semester3_ad_hours / package.nominal_hours]

        else:
            combined_item = [str(moduledata.module) + ' Admin Hours', ad_hours_proportion,
                             semester1_ad_hours, semester2_ad_hours, semester3_ad_hours]
        combined_list_modules.append(combined_item)

        if show_percentages:
            combined_item = [str(moduledata.module) + ' Assessment Hours',
                             100 * as_hours_proportion / package.nominal_hours,
                             100 * semester1_as_hours / package.nominal_hours,
                             100 * semester2_as_hours / package.nominal_hours,
                             100 * semester3_as_hours / package.nominal_hours]

        else:
            combined_item = [str(moduledata.module) + ' Assessment Hours', as_hours_proportion,
                             semester1_as_hours, semester2_as_hours, semester3_as_hours]
        combined_list_modules.append(combined_item)

        semester1_total += (semester1_c_hours + semester1_ad_hours + semester1_as_hours)
        semester2_total += (semester2_c_hours + semester2_ad_hours + semester2_as_hours)
        semester3_total += (semester3_c_hours + semester3_ad_hours + semester3_as_hours)

        # if show_percentages:
        #    semester1_total = semester1_total * 100 / package.nominal_hours
        #    semester2_total = semester2_total * 100 / package.nominal_hours
        #    semester3_total = semester3_total * 100 / package.nominal_hours

        total += c_hours_proportion + as_hours_proportion + ad_hours_proportion

    if show_percentages:
        semester1_total = semester1_total * 100 / package.nominal_hours
        semester2_total = semester2_total * 100 / package.nominal_hours
        semester3_total = semester3_total * 100 / package.nominal_hours
        total = 100 * total / package.nominal_hours

    template = loader.get_template('loads/activities.html')
    context = {
        'staff': staff,
        'combined_list': combined_list,
        'combined_list_modules': combined_list_modules,
        'semester1_total': semester1_total,
        'semester2_total': semester2_total,
        'semester3_total': semester3_total,
        'total': total,
        'package': package,
        'show_percentages': show_percentages
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
@permission_required('loads.view_assessmentstaff')
@permission_required('loads.add_assessmentstaff')
def assessmentstaff_index(request):
    """Allow viewing (and interface to add) AssessmentStaff"""
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package

    logger.info("[%s] (admin) assessment team viewed" % request.user, extra={'package': package})

    # Get all the staff who are currently on the assessment team
    assessment_staff = AssessmentStaff.objects.filter(package=package).order_by("staff")

    # And all the staff who are in the Package and could be added
    possible_assessment_staff = package.get_all_staff()

    # Because the view is so simple, we will add the "Create" view within it
    if request.method == 'POST':
        form = AssessmentStaffForm(request.POST, user=request.user)
        if form.is_valid():
            # Validation should ensure no duplicates and permissions are respected
            new_staff = form.cleaned_data['staff']
            new_package = form.cleaned_data['package']
            messages.success(request, 'Assessment Team member added successfully')
            logger.warning("[%s] (admin) added an assessment team member (%s to package %s)" % (request.user,
                           new_staff, new_package), extra={'form': form})
            form.save()
            url = reverse('assessmentstaff_index')
            return HttpResponseRedirect(url)

    else:
        form = AssessmentStaffForm(user=request.user)
        # Populate the package as a hidden variable, and restrict the queryset to those in the package
        form.fields['package'].initial = package
        form.fields['staff'].queryset = possible_assessment_staff

    template = loader.get_template('loads/assessmentstaff_list.html')
    context = {
        'staff': staff,
        'package': package,
        'possible_assessment_staff': possible_assessment_staff,
        'assessment_staff': assessment_staff,
        'form': form,
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
@permission_required('loads.delete_assessmentstaff')
def assessmentstaff_delete(request, assessmentstaff_id):
    """Delete an assessment resource, should not be possible for signed resources, except for superuser"""
    # Get the resource object
    assessmentstaff = get_object_or_404(AssessmentStaff, pk=assessmentstaff_id)

    # TODO: this is none too elegant, and could be outsourced
    # Fetch the staff user associated with the person requesting
    try:
        staff = Staff.objects.get(user=request.user)
    except Staff.DoesNotExist:
        staff = None

    # If neither here, time to boot
    if not staff:
        return HttpResponseRedirect(reverse('forbidden'))

    # Is this the current user's business?
    if assessmentstaff.package not in staff.get_all_packages(include_hidden=True):
        logger.info("[%s] (admin) assessment team package not in the user's packages" % request.user)
        return HttpResponseRedirect(reverse('forbidden'))
    else:
        messages.success(request, 'Assessment Team member removed successfully')
        logger.info("[%s] (admin) removed a member of the assessment team (%s)" % (request.user, assessmentstaff.staff))
        assessmentstaff.delete()

    url = reverse('assessmentstaff_index')
    return HttpResponseRedirect(url)


@login_required
def tasks_index(request):
    """Obtains a list of all non archived tasks"""
    # Fetch the tasks assigned against the specific user of the staff member
    staff = get_object_or_404(Staff, user=request.user)
    tasks = staff.get_all_tasks()
    # tasks = Task.objects.all().exclude(archive=True).order_by('deadline')

    augmented_tasks = []
    for task in tasks:
        augmented_tasks.append([task, task.is_urgent(), task.is_overdue()])

    logger.info("[%s] viewed their tasks" % request.user)
    template = loader.get_template('loads/tasks/index.html')
    context = {
        'augmented_tasks': augmented_tasks,
        'tasks_menu': True,
        'archived': False
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
def archived_tasks_index(request):
    """Obtains a list of all non archived tasks"""
    # Fetch the tasks assigned against the specific user of the staff member
    staff = get_object_or_404(Staff, user=request.user)
    tasks = staff.get_all_tasks(archived=True)
    # tasks = Task.objects.all().exclude(archive=True).order_by('deadline')

    augmented_tasks = []
    for task in tasks:
        augmented_tasks.append([task, task.is_urgent(), task.is_overdue()])

    logger.debug("[%s] viewed their archived tasks" % request.user)
    template = loader.get_template('loads/tasks/index.html')
    context = {
        'augmented_tasks': augmented_tasks,
        'tasks_menu': True,
        'archived': True
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
def tasks_bystaff(request, staff_id):
    """Show the tasks assigned against the specific user of the staff member"""
    staff = get_object_or_404(Staff, pk=staff_id)
    all_tasks = staff.get_all_tasks()

    logger.info("[%s] viewed the tasks assigned to %s" % (request.user, staff))
    # We will create separate lists for those tasks that are complete
    combined_list_complete = []
    combined_list_incomplete = []

    for task in all_tasks:
        # Is it complete? Look for a completion model
        completion = TaskCompletion.objects.all().filter(staff=staff).filter(task=task)
        if len(completion) == 0:
            combined_item = [task, task.is_urgent(), task.is_overdue()]
            combined_list_incomplete.append(combined_item)
        else:
            combined_item = [task, completion[0].when]
            combined_list_complete.append(combined_item)

    template = loader.get_template('loads/tasks/bystaff.html')
    context = {
        'staff': staff,
        'combined_list_complete': combined_list_complete,
        'combined_list_incomplete': combined_list_incomplete,
    }
    return HttpResponse(template.render(context, request))


@login_required()
def tasks_details(request, task_id):
    """Obtains a list of all completions for a given task"""
    # Get the task itself, and all targetted users
    task = get_object_or_404(Task, pk=task_id)

    logger.info("[%s] viewed details of task %s" % (request.user, task), extra={'task': task})
    all_targets = task.get_all_targets()

    combined_list_complete = []
    combined_list_incomplete = []

    for target in all_targets:
        # Is it complete? Look for a completion model
        completion = TaskCompletion.objects.all().filter(staff=target).filter(task=task)
        if len(completion) == 0:
            # Not complete, but only add the target if they aren't active
            if target.is_active():
                combined_item = [target, False]
                combined_list_incomplete.append(combined_item)
        else:
            combined_item = [target, completion[0]]
            combined_list_complete.append(combined_item)

    total_number = len(combined_list_complete) + len(combined_list_incomplete)
    if total_number > 0:
        percentage_complete = 100 * len(combined_list_complete) / total_number
    else:
        percentage_complete = 0

    template = loader.get_template('loads/tasks/details.html')
    context = {
        'task': task,
        'overdue': task.is_overdue(),
        'urgent': task.is_urgent(),
        'combined_list_complete': combined_list_complete,
        'combined_list_incomplete': combined_list_incomplete,
        'percentage_complete': percentage_complete
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
@admin_only
def custom_admin_index(request):
    """The beginnings of a more integrated admin menu"""

    logger.info("[%s] (admin) custom admin menu viewed" % request.user)
    template = loader.get_template('loads/admin/index.html')
    return HttpResponse(template.render({}, request))


@login_required
@staff_only
@admin_only
@permission_required('loads.add_staff')
def create_staff_user(request):
    """Allows for the creation of a Staff and linked User object"""

    if request.method == 'POST':
        form = StaffCreationForm(request.POST)
        if form.is_valid():
            form.save()
            new_username = form.cleaned_data['username']

            messages.success(request, 'Account created successfully')

            logger.info("[%s] (admin) created a staff user %s" % (request.user, new_username), extra={'form': form})
            url = reverse('custom_admin_index')
            return HttpResponseRedirect(url)

    else:
        form = StaffCreationForm()
        logger.info("[%s] (admin) opened form to create a staff user" % request.user)

    return render(request, 'loads/admin/create_staff_user.html', {'form': form})


@login_required
@staff_only
@admin_only
@permission_required('loads.add_externalexaminer')
def create_external_examiner(request):
    """Allows for the creation of an Examiner and linked User object"""

    if request.method == 'POST':
        form = ExternalExaminerCreationForm(request.POST)
        if form.is_valid():
            form.save()
            new_username = form.cleaned_data['username']

            messages.success(request, 'Account created successfully')
            logger.info("[%s] created an external examiner user %s" % (request.user, new_username), extra={'form': form})

            url = reverse('custom_admin_index')
            return HttpResponseRedirect(url)

    else:
        form = ExternalExaminerCreationForm()
        logger.info("[%s] (admin) opened form to create an external examiner user" % request.user)

    return render(request, 'loads/admin/create_external_examiner.html', {'form': form})


@login_required
def tasks_completion(request, task_id, staff_id):
    """Processes recording of a task completion"""
    # Get the task itself, and all targetted users
    # TODO: check for existing completions
    # TODO: check staff is in *open* targets
    task = get_object_or_404(Task, pk=task_id)
    staff = get_object_or_404(Staff, pk=staff_id)
    all_targets = task.get_all_targets()

    # check the staff member is that currently logged in
    # or a user with permission to edit completions
    is_current_user = (request.user == staff.user)
    can_override = request.user.has_perm('loads.add_taskcompletion')
    if not (is_current_user or can_override):
        logger.info("[%s] not the target user and has no override permission to complete task" % request.user)
        return HttpResponseRedirect(reverse('forbidden'))

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = TaskCompletionForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            new_item = form.save(commit=False)
            new_item.task = task
            new_item.staff = staff

            new_item.save()
            form.save_m2m()
            messages.success(request, 'Task marked as completed')
            logger.info("[%s] marked task %s complete for %s" % (request.user, task, staff), extra={'form': form})

            # redirect to the task details
            # TODO: which is a pain if we came from the bystaff view
            url = reverse('tasks_details', kwargs={'task_id': task_id})
            return HttpResponseRedirect(url)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = TaskCompletionForm()
        logger.info("[%s] opened task %s for %s" % (request.user, task, staff), extra={'form': form})

    return render(request, 'loads/tasks/completion.html', {'form': form, 'task': task,
                                                           'overdue': task.is_overdue(),
                                                           'urgent': task.is_urgent(), 'staff': staff})


@login_required
def add_assessment_resource(request, module_id):
    """
    Provide a form for uploading a module resource

    This will be used by module team members, and external examiners
    """
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # Get the module itself
    module = get_object_or_404(Module, pk=module_id)

    # Check for a valid permission at this stage
    # can_override = request.user.has_perm('loads.add_assessment_resource')
    # if not can_override:
    #    return HttpResponseRedirect(reverse('forbidden'))

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request
        form = AssessmentResourceForm(request.POST, request.FILES)

        # check whether it's valid:
        if form.is_valid():
            new_item = form.save(commit=False)
            new_item.owner = staff
            new_item.module = module

            new_item.save()
            form.save_m2m()
            logger.info("[%s] added an assessment resource for module %s in package %s" %
                        (request.user, module, module.package))

            url = reverse('modules_details', kwargs={'module_id': module_id})
            return HttpResponseRedirect(url)


    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = AssessmentResourceForm()
        logger.info("[%s] opened the form to add an assessment resource for module %s" % (request.user, module))

    return render(request, 'loads/modules/add_assessment_resource.html',
                  {'form': form, 'staff': staff, 'module': module})


@login_required
@staff_only
def module_staff_allocation(request, module_id, package_id):
    """Edit the allocation of staff to a module member"""

    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)
    # And the module we are going to act on
    module = get_object_or_404(Module, pk=module_id)
    # And the package we are going to act on
    package = get_object_or_404(WorkPackage, pk=package_id)

    # If either the logged in user or target user aren't in the package, this is forbidden
    if package not in user_staff.get_all_packages():
        logger.info("[%s] user is not a member of this package" % request.user)
        return HttpResponseRedirect(reverse('forbidden'))

    # The logged in user should be able to do this via the Admin interface, or disallow.
    permission = request.user.has_perm('loads.add_modulestaff') and request.user.has_perm(
        'loads.change_modulestaff') and request.user.has_perm('loads.delete_modulestaff')

    if not permission:
        logger.info("[%s] user has no permissions to alter allocations" % request.user)
        return HttpResponseRedirect(reverse('forbidden'))

    # Get a formset with only the choosable fields
    allocation_form_set = modelformset_factory(ModuleStaff, formset=BaseModuleStaffByModuleFormSet,
                                             fields=('staff', 'contact_proportion', 'admin_proportion',
                                                     'assessment_proportion'),
                                             can_delete=True)

    if request.method == "POST":
        formset = allocation_form_set(
            request.POST, request.FILES,
            queryset=ModuleStaff.objects.filter(package=package).filter(module=module).order_by(
                'staff__user__last_name')
        )
        # We need to tweak the queryset to only allow staff in the package
        for form in formset:
            form.fields['staff'].queryset = package.get_all_staff()
        if formset.is_valid():
            formset.save(commit=False)
            for form in formset:
                # Some fields are missing, so don't do a full save yet
                allocation = form.save(commit=False)
                # Fix the fields
                allocation.module = module
                allocation.package = package
            # Now do a real save
            formset.save(commit=True)
            logger.info("[%s] adjusted the module allocation for module %s" % (request.user, module), extra={'form': form})

            # redirect to the activites page
            # TODO this might just be a different package from this one, note.

            url = reverse('modules_details', args=[module_id])
            return HttpResponseRedirect(url)
    else:
        formset = allocation_form_set(queryset=ModuleStaff.objects.filter(package=package).filter(module=module).order_by(
            'staff__user__last_name'))
        # Again, only allow staff members in the package
        for form in formset:
            form.fields['staff'].queryset = package.get_all_staff()
        logger.info("[%s] opened the form for the module allocation for module %s" % (request.user, module), extra={'form': form})

    return render(request, 'loads/modules/allocations.html', {'module': module, 'package': package, 'formset': formset})


@login_required
@staff_only
def modules_index(request, semesters):
    """Shows a high level list of modules"""
    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = staff.package

    # By default, no programme or lead programme filter is set
    programme = None
    lead_programme = None
    # Don't show people by default
    show_people = False


    # Get all the modules in the package, pending further filtering
    modules = Module.objects.all().filter(package=package).order_by('module_code')

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request
        form = ModulesIndexForm(request.POST)
        form.fields['programme'].queryset = Programme.objects.all().filter(package=package)

        # check whether it's valid:
        if form.is_valid():
            semesters = form.cleaned_data['semesters']
            programme = form.cleaned_data['programme']
            lead_programme = form.cleaned_data['lead_programme']
            show_people = form.cleaned_data['show_people']

    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = ModulesIndexForm()
        # If semesters came via get, let's populate the form
        form.fields['semesters'].initial = semesters
        form.fields['programme'].queryset = Programme.objects.all().filter(package=package)


        # Check for any semester limitations, split by comma if something is actually there
    if semesters:
        valid_semesters = semesters.split(',')
    else:
        valid_semesters = list()


    combined_list = []
    for module in modules:
        # If there's a selected programme and this module isn't it, then skip
        if programme and module not in programme.modules.all():
            continue
        # And skip if lead programme is set, and this isn't the lead programme
        if programme and lead_programme and not (module.lead_programme == programme):
            continue
        # Is it valid for the semester, i.e. are and of its semesters in the passed in one?
        if len(valid_semesters):
            module_semesters = module.semester.split(',')
            valid_semester = False
            for m_sem in module_semesters:
                for v_sem in valid_semesters:
                    if m_sem == v_sem:
                        valid_semester = True
            if not valid_semester:
                continue

        # Store all relationships to the modules
        relationship = []

        # Is the logged in user on the teaching team?
        module_staff = ModuleStaff.objects.all().filter(module=module).filter(staff=staff)
        if len(module_staff):
            relationship.append('team_member')

        # Is the logged in user a moderator?
        if staff in module.moderators.all():
            relationship.append('moderator')

        # get the most recent assessment resource
        resources = AssessmentResource.objects.all().filter(module=module).order_by('-created')[:1]
        signoffs = AssessmentStateSignOff.objects.all().filter(module=module).order_by('-created')[:1]

        if len(resources) > 0:
            resource = resources[0]
        else:
            resource = False

        # Can the logged in user set a new assessment state?
        action_possible = False
        if len(signoffs) > 0:
            signoff = signoffs[0]
            for state in signoff.assessment_state.next_states.all():
                if state.can_be_set_by_staff(staff, module):
                    action_possible = True
        else:
            signoff = False

        combined_item = [module, relationship, resource, signoff, action_possible, module.get_lead_examiners()]
        combined_list.append(combined_item)

    logger.info("[%s] visited the modules index for package %s" % (request.user, package), extra={'form': form})
    template = loader.get_template('loads/modules/index.html')
    context = {
        'form': form,
        'combined_list': combined_list,
        'valid_semesters': valid_semesters,
        'package': package,
        'programme': programme,
        'lead_programme': lead_programme,
        'show_people': show_people,
    }
    return HttpResponse(template.render(context, request))


@login_required
@external_only
def external_modules_index(request, semesters):
    """Shows a high level list of modules to an external examiner"""
    # Fetch the staff user associated with the person requesting
    external = get_object_or_404(Staff, user=request.user)
    # And therefore the package enabled for that user
    package = external.package

    # By default, no programme or lead programme filter is set
    programme = None
    lead_programme = None
    # Don't show people by default
    show_people = False

    # Get the list of programmes that they examine
    examined_programmes = external.get_examined_programmes()

    # Get all the modules in the package, pending further filtering
    modules = Module.objects.all().filter(package=package).order_by('module_code')

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request
        form = ModulesIndexForm(request.POST)
        form.fields['programme'].queryset = examined_programmes

        # check whether it's valid:
        if form.is_valid():
            semesters = form.cleaned_data['semesters']
            programme = form.cleaned_data['programme']
            lead_programme = form.cleaned_data['lead_programme']
            show_people = form.cleaned_data['show_people']


    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = ModulesIndexForm()
        # If semesters came via get, let's populate the form
        form.fields['semesters'].initial = semesters
        form.fields['programme'].queryset = examined_programmes


        # Check for any semester limitations, split by comma if something is actually there
    if semesters:
        valid_semesters = semesters.split(',')
    else:
        valid_semesters = list()

    combined_list = []
    for module in modules:
        # Controversial... filter out modules not relevant
        if not external.can_examine_module(module):
            continue
        # If there's a selected programme and this module isn't it, then skip
        if programme and module not in programme.modules.all():
            continue
        # And skip if lead programme is set, and this isn't the lead programme
        if programme and lead_programme and not (module.lead_programme == programme):
            continue
        # Is it valid for the semester, i.e. are and of its semesters in the passed in one?
        if len(valid_semesters):
            module_semesters = module.semester.split(',')
            valid_semester = False
            for m_sem in module_semesters:
                for v_sem in valid_semesters:
                    if m_sem == v_sem:
                        valid_semester = True
            if not valid_semester:
                continue

        # Store all relationships to the modules
        relationship = []

        if module.lead_programme in examined_programmes:
            relationship.append('lead_external')
            # That's good enough, don't bother checking for other relations
        else:
            if any(programme in examined_programmes for programme in module.programmes.all()):
                relationship.append('external')

        # get the most recent assessment resource
        resources = AssessmentResource.objects.all().filter(module=module).order_by('-created')[:1]
        signoffs = AssessmentStateSignOff.objects.all().filter(module=module).order_by('-created')[:1]

        if len(resources) > 0:
            resource = resources[0]
        else:
            resource = False

        # Can the logged in user set a new assessment state?
        action_possible = False
        if len(signoffs) > 0:
            signoff = signoffs[0]
            for state in signoff.assessment_state.next_states.all():
                if state.can_be_set_by_external(external, module):
                    action_possible = True
        else:
            signoff = False

        combined_item = [module, relationship, resource, signoff, action_possible, module.get_lead_examiners()]
        combined_list.append(combined_item)

    logger.info("[%s] visited the external examiner modules index for package %s" % (request.user, package), extra={'form': form})
    template = loader.get_template('loads/modules/index.html')
    context = {
        'form': form,
        'external': external,
        'combined_list': combined_list,
        'package': package,
        'show_people': show_people,
    }
    return HttpResponse(template.render(context, request))


@login_required
def modules_details(request, module_id):
    """Detailed information on a given module"""
    # Get the module itself
    module = get_object_or_404(Module, pk=module_id)
    logger.info("[%s] seeking to examine the module details for %s" % (request.user, module))

    # Fetch the staff user associated with the person requesting
    try:
        staff = Staff.objects.get(user=request.user)

        if staff.is_external:
            if not staff.can_examine_module(module):
                logger.info("[%s] not an examiner for module %s" % (request.user, module))
                return HttpResponseRedirect(reverse('forbidden'))
        else:
            if not staff.user.is_superuser and not module.package in staff.get_all_packages(include_hidden=True):
                logger.info("[%s] module %s is not in user's packages" % (request.user, module))
                return HttpResponseRedirect(reverse('forbidden'))
    except Staff.DoesNotExist:
        staff = None

    # Get all associated activities and allocations
    activities = Activity.objects.all().filter(module=module).order_by('name')
    modulestaff = ModuleStaff.objects.all().filter(module=module)

    total_contact_proportion = 0
    total_admin_proportion = 0
    total_assessment_proportion = 0
    for allocation in modulestaff:
        total_contact_proportion += allocation.contact_proportion
        total_admin_proportion += allocation.admin_proportion
        total_assessment_proportion += allocation.assessment_proportion

    # Get all the sign offs and assessment history
    # There's a subtle bug in using just the history for help, so using signoffs too.
    assessment_history = module.get_assessment_history()
    # Get all signoffs to date
    assessment_signoffs = AssessmentStateSignOff.objects.all().filter(module=module).order_by('-created')

    # Detect if any assessment resources exist that are not signed
    unsigned_items = False
    # Check the most recent tuple of signoffs and items exists
    if assessment_history and assessment_history[0]:
        # If it does, get the signoff
        (signoff, items) = assessment_history[0]
        # If the signoff is None, it means the items are not signed
        if signoff is None:
            #there are unsigned items
            unsigned_items = True

    template = loader.get_template('loads/modules/details.html')
    context = {
        'module': module,
        'moderators': module.moderators.all(),
        'total_hours': module.get_all_hours(),
        'contact_hours': module.get_contact_hours(),
        'admin_hours': module.get_admin_hours(),
        'assessment_hours': module.get_assessment_hours(),
        'modulestaff': modulestaff,
        'activities': activities,
        'assessment_history': assessment_history,
        'assessment_signoffs': assessment_signoffs,
        'package': module.package,
        'total_contact_proportion': total_contact_proportion,
        'total_admin_proportion': total_admin_proportion,
        'total_assessment_proportion': total_assessment_proportion,
        'unsigned_items': unsigned_items,
    }
    return HttpResponse(template.render(context, request))


@login_required
def add_assessment_sign_off(request, module_id):
    """Detailed information on a given module"""
    # Get the module itself
    module = get_object_or_404(Module, pk=module_id)
    logger.info("[%s] seeking to add assessment sign off for module %s" % (request.user, module))

    # TODO: this is none too elegant, and could be outsourced
    # Fetch the staff user associated with the person requesting
    try:
        staff = Staff.objects.get(user=request.user)
        package = staff.package
    except Staff.DoesNotExist:
        staff = None

    # If neither here, time to boot
    if not staff:
        logger.info("[%s] has no staff object" % request.user)
        return HttpResponseRedirect(reverse('forbidden'))

    # Get all signoffs to date
    assessment_signoffs = AssessmentStateSignOff.objects.all().filter(module=module).order_by('-created')

    # Have we any already?
    if not len(assessment_signoffs):
        # No, so get all allowed initial states
        next_states = AssessmentState.objects.all().filter(initial_state=True)
    else:
        # There, are, so it's just the last object's sign off
        next_states = assessment_signoffs[0].assessment_state.next_states.all()

    # These are the possible successor states, but same may not be allowed to the current user
    for state in next_states:
        if not state.can_be_set_by(staff, module):
            next_states = next_states.exclude(pk=state.pk)

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = AssessmentStateSignOffForm(request.POST)

        # check whether it's valid:
        if form.is_valid():
            signoff = form.save(commit=False)
            signoff.signed_by = request.user
            signoff.module = module

            signoff.save()
            logger.info("[%s] signed off assessment states for module %s for package %s" %
                        (request.user, module, module.package), extra={'form': form})

            url = reverse('modules_details', kwargs={'module_id': module_id})
            return HttpResponseRedirect(url)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = AssessmentStateSignOffForm()
        form.fields['assessment_state'].queryset = next_states
        form.fields['signed_by'].initial = request.user
        form.fields['module'].initial = module
        logger.info("[%s] opened the assessment state sign off form for module %s for package %s" %
                    (request.user, module, module.package), extra={'form': form})


    template = loader.get_template('loads/modules/add_assessment_signoff.html')
    context = {
        'package': package,
        'module': module,
        'assessment_signoffs': assessment_signoffs,
        'next_states': next_states,
        'form': form
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
@permission_required('loads.del_assessmentstatesignoff')
def delete_assessment_sign_off(request, signoff_id, confirm=None):
    """
    Provides an interface for deleting an Assessment State Signed Off

    This should only be available to admins with sufficient permissions, only the last sign-off should be
    possible to delete, and only if there are not subsequent items.
    """
    # Get the signoff itself
    signoff = get_object_or_404(AssessmentStateSignOff, pk=signoff_id)
    logger.info("[%s] seeking to add assessment sign off for module %s" % (request.user, signoff.module))

    try:
        staff = Staff.objects.get(user=request.user)
    except Staff.DoesNotExist:
        staff = None

    if not staff:
        logger.info("[%s] has no staff object" % request.user)
        return HttpResponseRedirect(reverse('forbidden'))

    logger.warning("[%s] potentially deleting assessment signoff for module %s, package %s" %
                   (request.user, signoff.module, signoff.module.package), extra={'signoff': signoff})

    # Assume a lack of permissions
    permission = False

    if staff.user.is_superuser:
        permission = True
    elif staff.user.is_staff and request.user.has_perm('loads.del_assessmentstatesignoff'):
        permission = True
    elif signoff.module.package in staff.get_all_packages() and request.user.has_perm('loads.del_assessmentstatesignoff'):
        permission = True

    if not permission:
        logger.warning("no permission for deleting assessment signoff granted")
        messages.error(request, 'Sorry, you do not have administrative privileges for this action.')
        return HttpResponseRedirect(reverse('forbidden'))

    # Check for any more recent signoffs and if so, this is forbidden
    logger.debug("check for more recent signoffs")
    newer_signoffs = AssessmentStateSignOff.objects.all().filter(module=signoff.module).filter(created__gt=signoff.created)
    if len(newer_signoffs):
        messages.error(request, 'Only the most recent sign off may be deleted.')
        return HttpResponseRedirect(reverse('forbidden'))

    # Check for any more recent items than the signoff, and if this is so, this is forbidden
    logger.debug("check for more recent resources")
    newer_resources = AssessmentResource.objects.all().filter(module=signoff.module).filter(created__gt=signoff.created)
    if len(newer_resources):
        messages.error(request, 'Sign offs cannot be deleted after more recent items have been added.')
        return HttpResponseRedirect(reverse('forbidden'))


    # Check if the deletion is confirmed
    if not confirm:
        logger.debug("deletion not confirmed")
        context = {
            'signoff': signoff
        }
        template = loader.get_template('loads/modules/delete_assessment_signoff.html')
        logger.debug("template loaded")
        return HttpResponse(template.render(context, request))

    # If we are still here we can delete safely
    logger.warning("[%s] deleted assessment signoff for module %s, package %s" %
                   (request.user, signoff.module, signoff.module.package), extra={'signoff': signoff})
    signoff.delete()
    messages.info(request, 'Deleted assessment signoff.')

    url = reverse('modules_details', kwargs={'module_id': signoff.module.id})
    return HttpResponseRedirect(url)


@login_required
@staff_only
@permission_required('loads.add_modulestaff')
@permission_required('loads.change_modulestaff')
@permission_required('loads.delete_modulestaff')
def staff_module_allocation(request, staff_id, package_id):
    """Edit the allocation of modules to a staff member"""

    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)
    # And the staff member we are going to act on
    staff = get_object_or_404(Staff, pk=staff_id)
    # And the package we are going to act on
    package = get_object_or_404(WorkPackage, pk=package_id)

    logger.info("[%s] seeking to edit module allocation for %s in package %s" % (request.user, staff, package))

    # If either the logged in user or target user aren't in the package, this is forbidden
    if package not in user_staff.get_all_packages() or package not in staff.get_all_packages(include_hidden=True):
        logger.info("[%s] package not in user's package" % request.user)
        return HttpResponseRedirect(reverse('forbidden'))

    # Get a formset with only the choosable fields
    allocation_form_set = modelformset_factory(ModuleStaff, formset=BaseModuleStaffByStaffFormSet,
                                             fields=('module', 'contact_proportion', 'admin_proportion',
                                                     'assessment_proportion'),
                                             can_delete=True)

    if request.method == "POST":
        formset = allocation_form_set(
            request.POST, request.FILES,
            queryset=ModuleStaff.objects.filter(package=package).filter(staff=staff)
        )
        # We need to tweak the queryset to only allow modules in the package
        for form in formset:
            form.fields['module'].queryset = Module.objects.filter(package=package)
        if formset.is_valid():
            formset.save(commit=False)
            for form in formset:
                # Some fields are missing, so don't do a full save yet
                allocation = form.save(commit=False)
                # Fix the fields
                allocation.staff = staff
                allocation.package = package
            # Now do a real save
            formset.save(commit=True)
            logger.info("[%s] edited the module allocation for %s on package %s" %
                        (request.user, staff, package), extra={'form': form})

            # redirect to the activites page
            # TODO this might just be a different package from this one, note.

            url = reverse('activities', args=[staff_id])
            return HttpResponseRedirect(url)
    else:
        formset = allocation_form_set(queryset=ModuleStaff.objects.filter(package=package).filter(staff=staff))
        # Again, only allow modules in the package
        for form in formset:
            form.fields['module'].queryset = Module.objects.filter(package=package)

    return render(request, 'loads/staff/allocations.html', {'staff': staff, 'package': package, 'formset': formset})


@login_required
@staff_only
def generators_index(request):
    """Obtains a list of all ActivityGenerators in the User's selected WorkPackage"""

    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)
    # And the staff member we are going to act on
    staff = get_object_or_404(Staff, user=request.user)

    generators = ActivityGenerator.objects.all().filter(package=staff.package)

    logger.info("[%s] (admin) visited the generators index for package %s" % (request.user, staff.package))
    template = loader.get_template('loads/generators/index.html')
    context = {
        'generators': generators,
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
@permission_required('loads.add_activity')
def generators_generate_activities(request, generator_id):
    """(Re)generate all activities for a given Activity Generator"""

    # Fetch the staff user associated with the person requesting
    staff = get_object_or_404(Staff, user=request.user)
    # And the generator
    generator = get_object_or_404(ActivityGenerator, pk=generator_id)
    logger.info("[%s] seeking to generate activities for generator %u" % (request.user, generator.id))

    # If either the logged in user or target user aren't in the package, this is forbidden
    if generator.package not in staff.get_all_packages(include_hidden="True"):
        logger.info("[%s] package not in user's packages" % request.user)
        return HttpResponseRedirect(reverse('forbidden'))

    generator.generate_activities()
    messages.success(request, 'Activities Regenerated.')
    logger.info("[%s] (admin) triggered generator %s in package %s" % (request.user, generator, generator.package))
    url = reverse('generators_index')
    return HttpResponseRedirect(url)


@login_required
@staff_only
@admin_only
def projects_index(request):
    """Obtains a list of all non archived projects"""
    # Fetch the tasks assigned against the specific user of the staff member
    staff = get_object_or_404(Staff, user=request.user)
    projects = Project.objects.all()

    logger.info("[%s] (admin) visited the projects index" % request.user)
    template = loader.get_template('loads/projects/index.html')
    context = {
        'projects': projects,
    }
    return HttpResponse(template.render(context, request))


@login_required
@staff_only
@admin_only
@permission_required('loads.change_project')
@permission_required('loads.add_projectstaff')
@permission_required('loads.change_projectstaff')
@permission_required('loads.delete_projectstaff')
def projects_details(request, project_id):
    """Allows a Project and allocated staff to be edited"""

    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)

    # And the project we are going to act on
    project = get_object_or_404(Project, pk=project_id)
    package = user_staff.package

    # Get a formset with only the choosable fields
    ProjectStaffFormSet = modelformset_factory(ProjectStaff,  # formset=BaseModuleStaffByStaffFormSet,
                                               fields=('staff', 'start', 'end', 'hours_per_week'),
                                               widgets={'start' : DateInput(), 'end' : DateInput(),},
                                               can_delete=True)

    if request.method == "POST":
        project_form = ProjectForm(request.POST, instance=project)
        formset = ProjectStaffFormSet(
            request.POST, request.FILES,
            queryset=ProjectStaff.objects.filter(project=project),
        )
        if project_form.is_valid():
            project_form.save()

        if formset.is_valid():
            formset.save(commit=False)
            for form in formset:
                # Some fields are missing, so don't do a full save yet
                allocation = form.save(commit=False)
                # Fix the fields
                allocation.project = project
            # Now do a real save
            formset.save(commit=True)
            logger.info("[%s] (admin) edited the details for project %s" % (request.user, project),
                         extra={'form': form})

            # redirect to the activites page
            # TODO this might just be a different package from this one, note.

            url = reverse('projects_index')
            return HttpResponseRedirect(url)
    else:
        project_form = ProjectForm(instance=project)
        formset = ProjectStaffFormSet(queryset=ProjectStaff.objects.filter(project=project))
        for form in formset:
            form.fields['staff'].queryset = package.get_all_staff()
        logger.info("[%s] (admin) opened the details for project %s" % (request.user, project),
                    extra={'form': form})

    return render(request, 'loads/projects/allocations.html',
                  {'project': project, 'project_form': project_form, 'formset': formset})


@login_required
@staff_only
@admin_only
@permission_required('loads.add_projectstaff')
@permission_required('loads.change_projectstaff')
@permission_required('loads.delete_projectstaff')
def projects_generate_activities(request, project_id):
    """(Re)generate all activities for a project"""

    # Fetch the staff user associated with the person requesting
    user_staff = get_object_or_404(Staff, user=request.user)

    # And the project we are going to act on
    project = get_object_or_404(Project, pk=project_id)

    project.generate_activities()
    messages.success(request, 'Activities Regenerated.')
    logger.info("[%s] (admin) generated activities for project %s" % (request.user, project))

    url = reverse('projects_index')
    return HttpResponseRedirect(url)


@login_required()
def workpackage_change(request):
    """Allows a user to change their current active workpackage"""
    # TODO: Needs to allow External Examiners.
    # Get the member of staff for the logged in user
    staff = get_object_or_404(Staff, user=request.user)

    # Get all workpackages that touch on the staff member's group
    packages = staff.get_all_packages()

    logger.debug("[%s] changing package" % request.user)
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request and the given staff
        form = StaffWorkPackageForm(request.POST, instance=staff)
        form.fields['package'].queryset = packages
        # check whether it's valid:
        if form.is_valid():
            form.save()
            logger.info("[%s] changed package to %s", request.user, staff.package,
                         extra={'form': form})

            # Try to find where we came from
            next = next_page_pop(request)
            #TODO: Put the below handling into pop helper
            is_safe = url_has_allowed_host_and_scheme(url=next, allowed_hosts=request.get_host(),
                                                      require_https=request.is_secure())

            if not is_safe:
                logger.critical("[%s] used an invalid next page in package change" % request.user)

            if is_safe and next:
                return HttpResponseRedirect(next)
            else:
                # redirect to the loads page
                url = reverse('loads')
                return HttpResponseRedirect(url)

    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = StaffWorkPackageForm(instance=staff)
        form.fields['package'].queryset = packages
        try:
            #TODO: Sometimes Referer is not present, but I think this handling needs to be improved
            next_page_push(request, request.headers['Referer'])
        except KeyError:
            next_page_push(request, reverse('loads'))



    return render(request, 'loads/workpackage.html', {'form': form, 'staff': staff})


@login_required
@staff_only
@admin_only
@user_passes_test(lambda u: u.is_superuser)
def workpackage_migrate(request):
    """Allows a user to change their current active workpackage"""
    # Get the member of staff for the logged in user
    staff = get_object_or_404(Staff, user=request.user)

    # Get all workpackages that touch on the staff member's group
    packages = staff.get_all_packages()

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request and the given staff
        form = MigrateWorkPackageForm(request.POST)
        form.fields['source_package'].queryset = packages
        form.fields['destination_package'].queryset = packages

        # check whether it's valid:
        if form.is_valid():
            options = {
                'copy_programmes': form.cleaned_data['copy_programmes'],
                'copy_modules': form.cleaned_data['copy_modules'],
                'copy_modulestaff': form.cleaned_data['copy_modulestaff'],
                'copy_activities_generated': form.cleaned_data['copy_activities_generated'],
                'copy_activities_custom': form.cleaned_data['copy_activities_custom'],
                'copy_activities_modules': form.cleaned_data['copy_activities_modules'],
                'generate_projects': form.cleaned_data['generate_projects'], }

            destination_package = form.cleaned_data['destination_package']
            source_package = form.cleaned_data['source_package']
            logger.info("[%s] (admin) migrating package %s to %s" % (request.user, source_package, destination_package),
                         extra={'form': form})
            changes = destination_package.clone_from(source_package, options)
            logger.info("[%s] (admin) package %s to %s migration complete" % (request.user, source_package, destination_package),
                        extra={'form': form})

            template = loader.get_template('loads/workpackages/migrate_results.html')
            context = {
                'source_package': source_package,
                'destination_package': destination_package,
                'options': options,
                'changes': changes,
            }
            return HttpResponse(template.render(context, request))

    # if a GET (or any other method) we'll create a form from the current logged in user
    else:
        form = MigrateWorkPackageForm()
        form.fields['source_package'].queryset = packages
        form.fields['destination_package'].queryset = packages
        logger.info("[%s] (admin) package migration form opened" % request.user, extra={'form': form})

    return render(request, 'loads/workpackages/migrate.html', {'form': form, 'staff': staff})


# Class based views

class CreateTaskView(LoginRequiredMixin, CreateView):
    """View for creating a task"""
    model = Task
    success_url = reverse_lazy('tasks_index')
    fields = ['name', 'category', 'details', 'deadline', 'archive', 'targets', 'groups']

    def get_form(self, form_class=TaskForm):
        """
        We need to restrict form querysets
        """
        form = super(CreateTaskView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        # Get all the groups this person might use, by aggregating them from packages.
        packages = staff.get_all_packages()
        groups = Group.objects.all().filter(workpackage__in=packages).distinct()

        # Check if the staff member has permission to make tasks (in the admin interface)
        if staff.user.has_perm('loads.add_task'):
            # They are, so don't restrict the targets or groups any further
            form.fields['targets'].queryset = package_staff
            form.fields['groups'].queryset = groups
        else:
            # They are not, so the only allowable target is oneself
            form.fields['targets'].queryset = Staff.objects.all().filter(user=staff.user)
            form.fields['groups'].queryset = Group.objects.none()
        return form


class UpdateTaskView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """View for creating a task"""
    permission_required = 'loads.change_task'
    model = Task
    success_url = reverse_lazy('tasks_index')
    fields = ['name', 'category', 'details', 'deadline', 'archive', 'targets', 'groups']

    def get_form(self, form_class=None):
        """We need to restrict form querysets"""
        form = super(UpdateTaskView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        # Get all the groups this person might use, by aggregating them from packages.
        packages = staff.get_all_packages()
        groups = Group.objects.all().filter(workpackage__in=packages).distinct()

        form.fields['targets'].queryset = package_staff
        form.fields['groups'].queryset = groups
        return form

    # @method_decorator(permission_required('loads.change_task', raise_exception=True))
    # def dispatch(self, request):
    #    return super(UpdateTaskView, self).dispatch(request)


class CreateModuleView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """View for creating a Module"""
    permission_required = 'loads.add_module'
    model = Module
    fields = ['module_code', 'module_name', 'campus', 'size', 'semester', 'contact_hours', 'admin_hours',
              'assessment_hours',
              'coordinator', 'moderators', 'programmes', 'lead_programme']

    def get_form(self, form_class=None):
        """We need to restrict form querysets"""
        form = super(CreateModuleView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        # Work out the programmes in the package
        package_programmes = Programme.objects.all().filter(package=package)

        # And restrict the querysets as appropriate
        form.fields['coordinator'].queryset = package_staff
        form.fields['moderators'].queryset = package_staff
        form.fields['programmes'].queryset = package_programmes
        form.fields['lead_programme'].queryset = package_programmes
        return form

    def form_valid(self, form):
        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package

        self.object = form.save(commit=False)
        self.object.package = package
        response = super(CreateModuleView, self).form_valid(form)
        return response

    def get_success_url(self):
        """Send us back to the details view"""
        return reverse('modules_details', kwargs={'module_id': self.object.pk})


class UpdateModuleView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """View for editing a Module"""
    permission_required = 'loads.change_module'
    model = Module
    fields = ['module_code', 'module_name', 'campus', 'size', 'semester', 'contact_hours', 'admin_hours',
              'assessment_hours',
              'coordinator', 'moderators', 'programmes', 'lead_programme']

    def get_form(self, form_class=None):
        """We need to restrict form querysets"""
        form = super(UpdateModuleView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        # Work out the programmes in the package
        package_programmes = Programme.objects.all().filter(package=package)

        # And restrict the querysets as appropriate
        form.fields['coordinator'].queryset = package_staff
        form.fields['moderators'].queryset = package_staff
        form.fields['programmes'].queryset = package_programmes
        form.fields['lead_programme'].queryset = package_programmes
        return form

    def get_success_url(self):
        """Send us back to the details view"""
        return reverse('modules_details', kwargs={'module_id': self.object.pk})


class CreateProgrammeView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """View for creating a Programme"""
    permission_required = 'loads.add_programme'
    model = Programme
    success_url = reverse_lazy('programmes_index')
    fields = ['programme_code', 'programme_name', 'examiners', 'directors']

    def get_form(self, form_class=None):
        form = super(CreateProgrammeView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        form.fields['directors'].queryset = package_staff
        return form

    def form_valid(self, form):
        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package

        self.object = form.save(commit=False)
        self.object.package = package
        response = super(CreateProgrammeView, self).form_valid(form)
        return response


class DetailsProgrammeView(LoginRequiredMixin, DetailView):
    """View for editing a Programme"""
    model = Programme
    success_url = reverse_lazy('programmes_index')
    fields = ['programme_code', 'programme_name', 'examiners', 'directors']

    def get_queryset(self):
        try:
            staff = Staff.objects.get(user=self.request.user)
            package = staff.package
        except Staff.DoesNotExist:
            raise PermissionDenied("""Your user has no matching staff object.
            This is likely to be because no account has been created for you.""")
        else:
            return Programme.objects.all().filter(package=package)


class UpdateProgrammeView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """View for editing a Programme"""
    permission_required = 'loads.change_programme'
    model = Programme
    success_url = reverse_lazy('programmes_index')
    fields = ['programme_code', 'programme_name', 'examiners', 'directors']

    def get_form(self, form_class=None):
        form = super(UpdateProgrammeView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        form.fields["directors"].queryset = package_staff
        return form


class ProgrammeList(LoginRequiredMixin, ListView):

    """Generic view for Programme List"""
    model = Programme
    context_object_name = 'programmes'

    def get_queryset(self):
        try:
            staff = Staff.objects.get(user=self.request.user)
            package = staff.package
        except Staff.DoesNotExist:
            raise PermissionDenied("""Your user has no matching staff object.
            This is likely to be because no account has been created for you.""")
        else:
            return Programme.objects.all().filter(package=package)


 # Looks like decorators execute before mixins, so if you don't call the login decorator, the staff_only may fail
@method_decorator(login_required, name='dispatch')
@method_decorator(staff_only, name='dispatch')
class ActivityListView(LoginRequiredMixin, ListView):
    """
    Generic view for the Activities List
    """
    model = Activity
    context_object_name = 'activities'

    def get_queryset(self):
        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package

        return Activity.objects.all().filter(package=package).order_by("staff", "name")


class CreateActivityView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """View for creating an Activity"""
    permission_required = 'loads.add_activity'
    model = Activity
    success_url = reverse_lazy('activities_index')
    fields = ['name', 'hours', 'percentage', 'hours_percentage',
              'semester', 'activity_type', 'module', 'staff', 'comment']

    def get_form(self, form_class=None):
        form = super(CreateActivityView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        form.fields['staff'].queryset = package_staff
        form.fields['module'].queryset = Module.objects.all().filter(package=package)
        return form

    def form_valid(self, form):
        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package

        self.object = form.save(commit=False)
        self.object.package = package
        response = super(CreateActivityView, self).form_valid(form)
        return response


class UpdateActivityView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """View for updating an Activity"""
    permission_required = 'loads.change_activity'
    model = Activity
    success_url = reverse_lazy('activities_index')
    fields = ['name', 'hours', 'percentage', 'hours_percentage',
              'semester', 'activity_type', 'module', 'staff', 'comment']

    def get_form(self, form_class=None):
        form = super(UpdateActivityView, self).get_form(form_class)

        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package
        package_staff = package.get_all_staff()

        form.fields['staff'].queryset = package_staff
        form.fields['module'].queryset = Module.objects.all().filter(package=package)
        return form

    def form_valid(self, form):
        # Work out the correct package and the staff within in
        staff = get_object_or_404(Staff, user=self.request.user)
        package = staff.package

        self.object = form.save(commit=False)
        self.object.package = package
        response = super(UpdateActivityView, self).form_valid(form)
        return response
