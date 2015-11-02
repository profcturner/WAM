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

# And code to handle timezones
from django.utils.timezone import utc
import datetime

class Command(BaseCommand):
    help = 'Emails staff if tasks are outstanding'

    def add_arguments(self, parser):
        parser.add_argument('--urgent-only',
            action='store_true',
            dest='urgent-only',
            default=False,
            help='Only email if some tasks are urgent (less than 7 days to deadline)')

            
    def handle(self, *args, **options):
        #TODO needs some decent exception handling
        all_staff = Staff.objects.all()
        
        count = 0
        urgent_only = options['urgent-only']
        for staff in all_staff:
            if self.email_tasks_by_staff(staff, urgent_only=urgent_only):
                count += 1

        self.stdout.write(str(count)+ ' reminder(s) sent')


    def email_tasks_by_staff(self, staff, urgent_only='false'):
        """docstring for email_tasks_by_staff"""
        all_tasks = staff.get_all_tasks()

        # We will create separate lists for those tasks that are complete
        combined_list_complete = []
        combined_list_incomplete = []
        
        urgent_tasks = False
        now = datetime.datetime.utcnow().replace(tzinfo=utc)
        for task in all_tasks:
            # Is it complete? Look for a completion model
            completion = TaskCompletion.objects.all().filter(staff=staff).filter(task=task)
            if len(completion) == 0:
                # It isn't complete...
                combined_item = [task, False]
                combined_list_incomplete.append(combined_item)
                # How long do we have left
                seconds_left = (task.deadline - now).total_seconds()
                # If a task is less than a week from deadline consider it urgent
                if(seconds_left < 60*60*24*7):
                    urgent_tasks = True
            else:
                combined_item = [task, completion[0].when]
                combined_list_complete.append(combined_item)
                
        # Don't nag staff with no tasks
        if len(combined_list_incomplete) == 0:
            return False
        
        # Or if urgency is set to low and no tasks are urgent
        if not urgent_tasks and urgent_only:
            return False 
        
        plaintext = get_template('loads/emails/task_reminders.txt')
        html = get_template('loads/emails/task_reminders.html')

        context = Context({
            'staff': staff,
            'combined_list_incomplete': combined_list_incomplete,
            'combined_list_complete': combined_list_complete,
            'urgent_tasks': urgent_tasks,
            'urgent_only' : urgent_only, 
        })

        # TODO Remove hardcode from address
        subject, from_email, to = 'Your task reminders', 'c.turner@ulster.ac.uk', staff.user.email
        text_content = plaintext.render(context)
        html_content = html.render(context)
        
        self.stdout.write('Email sent to ' + staff.user.email)
        
        email = EmailMultiAlternatives(subject, text_content, from_email, [to])
        email.attach_alternative(html_content, "text/html")
        email.send()
        return True


    