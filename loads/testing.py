"""
Helpers for building test data, shared by the test modules.

These keep individual tests short and readable. Every User created fires the
post_save signal in loads.signals, which creates the linked Staff object.
"""
import datetime

from django.contrib.auth.models import User, Group, Permission

from .models import (ActivityType, AssessmentResourceType, AssessmentStaff, AssessmentState, Campus,
                     Category, Module, ModuleStaff, Programme, Staff, WorkPackage)


def make_package(name="2017/18", group=None, **kwargs):
    """A WorkPackage, optionally visible to members of group"""
    defaults = dict(details="", startdate=datetime.date(2017, 9, 1), enddate=datetime.date(2018, 8, 31))
    defaults.update(kwargs)
    package = WorkPackage.objects.create(name=name, **defaults)
    if group:
        package.groups.add(group)
    return package


def make_staff(username, package=None, group=None, is_external=False, superuser=False,
               is_staff=False, permissions=(), password=None, **user_fields):
    """A User and its Staff object. Without a password, log in with Client.force_login()"""
    if superuser:
        user = User.objects.create_superuser(username, f"{username}@example.ac.uk", password, **user_fields)
    else:
        user = User.objects.create_user(username, f"{username}@example.ac.uk", password,
                                        is_staff=is_staff, **user_fields)
    if group:
        user.groups.add(group)
    for codename in permissions:
        app_label, codename = codename.split('.')
        user.user_permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))

    staff = Staff.objects.get(user=user)
    staff.is_external = is_external
    staff.package = package
    staff.save()
    return staff


def make_activity_type(name="Lecturing", category_name="Education"):
    category, _ = Category.objects.get_or_create(name=category_name,
                                                 defaults={'abbreviation': category_name.lower(), 'colour': 'red'})
    return ActivityType.objects.create(name=name, category=category)


def make_module(package, code="COM101", semester="1", **kwargs):
    campus = kwargs.pop('campus', None) or Campus.objects.get_or_create(name="Campus")[0]
    defaults = dict(module_name=f"Module {code}", credits=20, number_students=100)
    defaults.update(kwargs)
    return Module.objects.create(module_code=code, package=package, campus=campus, semester=semester, **defaults)


def make_programme(package, code="P1", examiners=()):
    programme = Programme.objects.create(programme_code=code, programme_name=f"Programme {code}", package=package)
    programme.examiners.add(*examiners)
    return programme


def allocate(staff, module, contact=100, admin=100, assessment=100, activity_type=None):
    """Allocate staff to a module. (ModuleStaff.activity_type otherwise defaults to an id that may not exist)"""
    if activity_type is None:
        activity_type = ActivityType.objects.first() or make_activity_type()
    return ModuleStaff.objects.create(staff=staff, module=module, package=module.package,
                                      contact_proportion=contact, admin_proportion=admin,
                                      assessment_proportion=assessment, activity_type=activity_type)


def make_state(name="Ready", actors="coordinator", **kwargs):
    defaults = dict(description=name, notify="coordinator", priority=1, initial_state=True)
    defaults.update(kwargs)
    return AssessmentState.objects.create(name=name, actors=actors, **defaults)


def make_resource_type(name="Exam"):
    return AssessmentResourceType.objects.create(name=name)


def make_group(name="School"):
    return Group.objects.create(name=name)


def add_assessment_staff(staff, package):
    return AssessmentStaff.objects.create(staff=staff, package=package)
