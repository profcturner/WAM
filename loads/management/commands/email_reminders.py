'''A custom command to send reminder emails for open tasks to staff'''
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
from loads.models import Task
from loads.models import TaskCompletion

# We need to access a few settings
from django.conf import settings

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
            if self.email_tasks_by_staff(staff, options, urgent_only=urgent_only):
                count += 1

        if verbosity:
            self.stdout.write(str(count)+ ' reminder(s) sent')
        
        if verbosity and options['test-only']:
            self.stdout.write('TEST MODE, No emails will actually be sent.')
            


    def email_tasks_by_staff(self, staff, options, urgent_only='false'):
        """docstring for email_tasks_by_staff"""
        verbosity = options['verbosity']
        
        # If the member of staff is inactive (perhaps retired, skip them)
        if not staff.is_active():
          if verbosity > 2:
            self.stdout.write('  considering: {}'.format(str(staff)))
            self.stdout.write('    user marked inactive, skipping...')
          return False

        # Get all the tasks for this member of staff who must be active now
        all_tasks = staff.get_all_tasks()

        # We will create separate lists for those tasks that are complete
        combined_list_complete = []
        combined_list_incomplete = []
        
        urgent_tasks = False
        for task in all_tasks:
            # Is it complete? Look for a completion model
            completion = TaskCompletion.objects.all().filter(staff=staff).filter(task=task)
            if len(completion) == 0:
                # It isn't complete, find out if urgent or overdue
                urgent = task.is_urgent()
                overdue = task.is_overdue()

                if urgent:
                    urgent_tasks = True
                    
                # It isn't complete...
                combined_item = [task, urgent, overdue]
                combined_list_incomplete.append(combined_item)
                # How long do we have left
                
            else:
                # It is complete, add information as to when
                combined_item = [task, completion[0].when]
                combined_list_complete.append(combined_item)
        
        if verbosity > 2:
            self.stdout.write('  considering: {}'.format(str(staff)))
            self.stdout.write('    complete {}, incomplete {}, urgent tasks {}'.format(
                len(combined_list_complete), len(combined_list_incomplete), urgent_tasks
            ))
                    
        # Don't nag staff with no tasks
        if len(combined_list_incomplete) == 0:
            return False
        
        # Or if urgent_only is set and no tasks are urgent
        if not urgent_tasks and urgent_only:
            return False 
        
        plaintext = get_template('loads/emails/task_reminders.txt')
        html = get_template('loads/emails/task_reminders.html')

        context_dict = {
            'staff': staff,
            'combined_list_incomplete': combined_list_incomplete,
            'combined_list_complete': combined_list_complete,
            'urgent_tasks': urgent_tasks,
            'urgent_only' : urgent_only,
            'base_url' : settings.WAM_URL, 
        };

        if urgent_tasks:
            email_subject = 'URGENT: Your task reminders'
        else:
            email_subject = 'Your task reminders'
            
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


    