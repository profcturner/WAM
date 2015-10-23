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

class Command(BaseCommand):
    help = 'Emails staff if tasks are outstanding'

    #def add_arguments(self, parser):
    #    parser.add_argument('poll_id', nargs='+', type=int)

    def handle(self, *args, **options):
        #TODO needs some decent exception handling
        all_staff = Staff.objects.all()
        
        for staff in all_staff:
            self.email_tasks_by_staff(staff)

        self.stdout.write('Reminders sent')


    def email_tasks_by_staff(self, staff):
        """docstring for email_tasks_by_staff"""
        #TODO Too much commonality with view layer, move some to model
        user_tasks = Task.objects.all().filter(targets=staff).exclude(archive=True).distinct().order_by('deadline')
    
        # And those assigned against the group
        groups = Group.objects.all().filter(user=staff.user)
        group_tasks = Task.objects.all().filter(groups__in=groups).distinct().order_by('deadline')
    
        # Combine them
        all_tasks = user_tasks | group_tasks

        # We will create separate lists for those tasks that are complete
        combined_list_complete = []
        combined_list_incomplete = []
    
        for task in all_tasks:
            # Is it complete? Look for a completion model
            completion = TaskCompletion.objects.all().filter(staff=staff).filter(task=task)
            if len(completion) == 0:
                combined_item = [task, False]
                combined_list_incomplete.append(combined_item)
            else:
                combined_item = [task, completion[0].when]
                combined_list_complete.append(combined_item)
                
        if len(combined_list_incomplete) == 0:
            # Don't nag staff with no tasks
            return False
        
        plaintext = get_template('loads/emails/task_reminders.txt')
        html     = get_template('loads/emails/task_reminders.html')

        context = Context({
            'staff': staff,
            'combined_list_incomplete': combined_list_incomplete,
            'combined_list_complete': combined_list_complete, 
        })

        # TODO Remove hardcode from address
        subject, from_email, to = 'Your task reminders', 'c.turner@ulster.ac.uk', staff.user.email
        text_content = plaintext.render(context)
        html_content = html.render(context)
        
        self.stdout.write('Email sent to ' + staff.user.email)
        
        email = EmailMultiAlternatives(subject, text_content, from_email, [to])
        email.attach_alternative(html_content, "text/html")
        email.send()


    