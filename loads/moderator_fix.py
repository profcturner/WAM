from .models import WorkPackage
from .models import Module


def copy_moderators(source_workpackage, destination_workpackage):
    """Fixes the lack of cloned moderators"""

    source_modules = Module.objects.all().filter(package=source_workpackage)
    destination_modules = Module.objects.all().filter(package=destination_workpackage)

    for source_module in source_modules:
        print("Looking at {}".format(source_module))
        # Is there a destination module with the correct code?
        destination_module = destination_modules.filter(module_code=source_module.module_code)[0]

        if not destination_module:
            print('!! No matching destination module')
            continue
        else:
            # Get the moderators
            moderators = source_module.moderators
            for moderator in moderators:
                print('   Adding Moderator {}'.format(moderator))
                #destination_module.moderators.add(moderator)
            #destination_module.save()

    print('Done')


