'''A custom command to send assessment resource updates to staff'''
# Code to implement a custom command
from django.core.management.base import BaseCommand, CommandError

# We need to manipulate User and Group Information
from django.contrib.auth.models import User, Group

# We will be using mail functionality, and templates to create them
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.template import Context

# And some models
from loads.models import Staff
from loads.models import Programme
from loads.models import Module
from loads.models import AssessmentResource
from loads.models import ExternalExaminer

# We need to access a few settings
from django.conf import settings

import datetime
# code to handle timezones
from django.utils import timezone

class Command(BaseCommand):
    help = 'Emails staff if tasks are outstanding'

    def add_arguments(self, parser):
        parser.add_argument('--urgent-only',
            action='store_true',
            dest='urgent-only',
            default=False,
            help='Only email if some tasks are urgent (less than 7 days to deadline)')
            
        parser.add_argument('--test-only',
            action='store_true',
            dest='test-only',
            default=False,
            help='Don\'t actually send emails')
            
        parser.add_argument('--include-past',
            action='store_true',
            dest='include-past',
            default=False,
            help='Include notifications from work packages in the past')

            
    def handle(self, *args, **options):
        #TODO needs some decent exception handling
        all_staff = Staff.objects.all()
        all_examiners = ExternalExaminer.objects.all()
        
        count = 0
        urgent_only = options['urgent-only']
        verbosity = options['verbosity']
        
        if verbosity and options['test-only']:
            self.stdout.write('TEST MODE, No emails will actually be sent.')
        
        for staff in all_staff:
            if self.email_updates_by_staff(staff, options, urgent_only=urgent_only):
                count += 1

        for external in all_examiners:
            if self.email_updates_by_external(external, options, urgent_only=urgent_only):
                count += 1

        if verbosity:
            self.stdout.write(str(count)+ ' update(s) sent')
        
        if verbosity and options['test-only']:
            self.stdout.write('TEST MODE, No emails will actually be sent.')
            


    def email_updates_by_staff(self, staff, options, urgent_only='false'):
        """email and updates to an individual staff member"""
        verbosity = options['verbosity']
        include_past = options['include-past']
        
        # If the member of staff is inactive (perhaps retired, skip them)
        if not staff.is_active():
          if verbosity > 2:
            self.stdout.write('  considering: {}'.format(str(staff)))
            self.stdout.write('    user marked inactive, skipping...')
          return False
        
        # When did the person last login?
        last_login = staff.user.last_login
        
        # Work out when the person last logged in to see what's considered new
        if last_login == None:
            # To prevent type errors create a date to compare against in this case
            census_date = datetime.datetime(1970, 1, 1)
            census_date = timezone.make_aware(census_date, timezone.get_current_timezone())
            last_login = "never"
        else:
            census_date = last_login

 
        # Get all the modules for which this staff member is a coordinator
        coordinated = Module.objects.all().filter(coordinator=staff)
        if not options['include-past']:
            now = datetime.datetime.today().date()
            coordinated = coordinated.filter(package__enddate__lte=now)
                
        coordinated_items = AssessmentResource.objects.all().filter(created__gte=census_date).filter(module__in=coordinated).distinct()
        
        # Get all the modules for which this staff member is a moderator
        moderated = Module.objects.all().filter(moderators=staff)
        if not options['include-past']:
            now = datetime.datetime.today().date()
            moderated = moderated.filter(package__enddate__lte=now)
                
        moderated_items = AssessmentResource.objects.all().filter(created__gte=census_date).filter(module__in=moderated).distinct()
        
        if verbosity > 2:
            self.stdout.write('  considering: {}'.format(str(staff)))
            self.stdout.write('    last login time: {}, census date: {}'.format(last_login, census_date))
            self.stdout.write('    coordinated modules {}, coordinated items {}'.format(
                len(coordinated), len(coordinated_items)
            ))
            self.stdout.write('    moderated modules {}, moderated items {}'.format(
                len(moderated), len(moderated_items)
            ))
                    
        # Don't nag staff with no items
        if len(coordinated_items)+len(moderated_items) == 0:
            return False

        plaintext = get_template('loads/emails/assessment_updates.txt')
        html = get_template('loads/emails/assessment_updates.html')

        context_dict = {
            'staff': staff,
            'coordinated_items': coordinated_items,
            'moderated_items': moderated_items,
            'external_examiner': False,
            'base_url' : settings.WAM_URL, 
        };

        email_subject = 'You have new assessment items to consider'
            
        from_email, to = settings.WAM_AUTO_EMAIL_FROM, staff.user.email
        text_content = plaintext.render(context_dict)
        html_content = html.render(context_dict)
        
        if verbosity:
            self.stdout.write('Email sent to {} <{}>'.format(str(staff), staff.user.email))
        
        email = EmailMultiAlternatives(email_subject, text_content, from_email, [to])
        email.attach_alternative(html_content, "text/html")
        if not options['test-only']:
            email.send()
        return True


    def email_updates_by_external(self, external, options, urgent_only='false'):
        """email and updates to an individual external examiner"""
        verbosity = options['verbosity']
        
        # If the member of staff is inactive (perhaps retired, skip them)
        if not external.is_active():
          if verbosity > 2:
            self.stdout.write('  considering: {}'.format(str(external)))
            self.stdout.write('    user marked inactive, skipping...')
          return False
        
        # When did the person last login?
        last_login = external.user.last_login
        
        if last_login == None:
            census_date = datetime.datetime(1970, 1, 1)
            census_date = timezone.make_aware(census_date, timezone.get_current_timezone())
            last_login = "never"
        else:
            census_date = last_login
            
        # Get moderated programmes
        programmes = external.get_examined_programmes()
        
        # Get all the modules for which this staff member is the lead examiner
        examined_modules = Module.objects.all().filter(lead_programme__in=programmes).distinct()
        if not options['include-past']:
            now = datetime.datetime.today().date()
            examined_modules = examined_modules.filter(package__enddate__lte=now)
        
        examined_items = AssessmentResource.objects.all().filter(created__gte=census_date).filter(module__in=examined_modules).distinct()
        
        if verbosity > 2:
            self.stdout.write('  considering: {}'.format(str(external)))
            self.stdout.write('    (External Examiner)')
            self.stdout.write('    last login time: {}, census date: {}'.format(last_login, census_date))
            self.stdout.write('    examined modules {}, examined items {}'.format(
                len(examined_modules), len(examined_items)
            ))
                    
        # Don't nag staff with no items
        if len(examined_items) == 0:
            return False

        plaintext = get_template('loads/emails/assessment_updates.txt')
        html = get_template('loads/emails/assessment_updates.html')

        context_dict = {
            'staff': external,
            'examined_items': examined_items,
            'external_examiner': True,
            'base_url' : settings.WAM_URL, 
        };

        email_subject = 'You have new assessment items to consider'
            
        from_email, to = settings.WAM_AUTO_EMAIL_FROM, external.user.email
        text_content = plaintext.render(context_dict)
        html_content = html.render(context_dict)
        
        if verbosity:
            self.stdout.write('Email sent to {} <{}>'.format(str(external), external.user.email))
        
        email = EmailMultiAlternatives(email_subject, text_content, from_email, [to])
        email.attach_alternative(html_content, "text/html")
        if not options['test-only']:
            email.send()
        return True



    