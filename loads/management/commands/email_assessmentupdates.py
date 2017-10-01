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

            
    def handle(self, *args, **options):
        #TODO needs some decent exception handling
        all_staff = Staff.objects.all()
        
        count = 0
        urgent_only = options['urgent-only']
        verbosity = options['verbosity']
        
        if verbosity and options['test-only']:
            self.stdout.write('TEST MODE, No emails will actually be sent.')
        
        for staff in all_staff:
            if self.email_updates_by_staff(staff, options, urgent_only=urgent_only):
                count += 1

        if verbosity:
            self.stdout.write(str(count)+ ' update(s) sent')
        
        if verbosity and options['test-only']:
            self.stdout.write('TEST MODE, No emails will actually be sent.')
            


    def email_updates_by_staff(self, staff, options, urgent_only='false'):
        """email and updates to an individual staff member"""
        verbosity = options['verbosity']
        
        # If the member of staff is inactive (perhaps retired, skip them)
        if not staff.is_active():
          if verbosity > 2:
            self.stdout.write('  considering: {}'.format(str(staff)))
            self.stdout.write('    user marked inactive, skipping...')
          return False
        
        # When did the person last login?
        last_login = staff.user.last_login
        
        if last_login == None:
            census_date = datetime.datetime(1970, 1, 1)
            census_date = timezone.make_aware(census_date, timezone.get_current_timezone())
            last_login = "never"
        else:
            census_date = last_login
        
        # Is this person listed as an external examiner?
        examiners = ExternalExaminer.objects.all().filter(user=staff.user)
        programmes = Programme.objects.all().filter(examiners__in=examiners).distinct()
        if len(programmes):
            external_examiner = True
        else:
            external_examiner = False
          
        # TODO: Get all the modules for which this staff member is a coordinator

        # Get all the modules for which this staff member is a moderator
        moderated = Module.objects.all().filter(moderators=staff)
        
        # Get all the modules for which this staff member is the lead examiner
        examined = Module.objects.all().filter(lead_programme__in=programmes).distinct()
        
        moderated_items = AssessmentResource.objects.all().filter(created__gte=census_date).filter(module__in=moderated).distinct()
        examined_items = AssessmentResource.objects.all().filter(created__gte=census_date).filter(module__in=examined).distinct()
        
        if verbosity > 2:
            self.stdout.write('  considering: {}'.format(str(staff)))
            if external_examiner:
                self.stdout.write('    (External Examiner)')
            self.stdout.write('    last login time: {}, census date: {}'.format(last_login, census_date))
            self.stdout.write('    moderated modules {}, examined modules {}, moderated items {}, examined items {}'.format(
                len(moderated), len(examined), len(moderated_items), len(examined_items)
            ))
                    
        # Don't nag staff with no items
        if len(moderated_items)+len(examined_items) == 0:
            return False

        plaintext = get_template('loads/emails/assessment_updates.txt')
        html = get_template('loads/emails/assessment_updates.html')

        context_dict = {
            'staff': staff,
            'moderated_items': moderated_items,
            'examined_items': examined_items,

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


    