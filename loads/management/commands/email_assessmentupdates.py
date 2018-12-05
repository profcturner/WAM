"""A custom command to send assessment resource updates to staff"""
# Code to implement a custom command
from django.core.management.base import BaseCommand

# We will be using mail functionality, and templates to create them
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template

# And some models
from loads.models import ModuleStaff
from loads.models import AssessmentStaff
from loads.models import AssessmentStateSignOff

# We need to access a few settings
from django.conf import settings

import datetime
# code to handle timezones
from django.utils.timezone import utc


class Command(BaseCommand):
    help = 'Emails assessment sign-off details to relevant staff and examiners'

    def add_arguments(self, parser):
        parser.add_argument('--quiet',
                            action='store_true',
                            dest='quiet',
                            default=False,
                            help='Don\'t produce output if nothing is to be done')

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
        # TODO needs some decent exception handling

        # Get all sign offs with no notification time
        signoffs = AssessmentStateSignOff.objects.all().filter(notified=None).order_by("created")

        count = 0
        verbosity = options['verbosity']
        include_past = options['include-past']
        quiet = options['quiet']
        # TODO: quiet needs better handling, really

        if verbosity and options['test-only']:
            self.stdout.write(self.style.WARNING('TEST MODE, No emails will actually be sent.'))

        for signoff in signoffs:
            if signoff.module.package.in_the_past() and not include_past:
                if verbosity:
                    self.stdout.write('Skipping sign-off for package in the past:')
                    self.stdout.write('  {} {}'.format(signoff.assessment_state, signoff.created))
            else:
                if self.email_updates_for_signoff(signoff, options):
                    count += 1

        if not quiet:
            self.stdout.write(str(count) + ' update(s) sent')

        if verbosity and options['test-only']:
            self.stdout.write(self.style.WARNING('TEST MODE, No emails will actually be sent.'))

    def email_updates_for_signoff(self, signoff, options):
        """Email relevant parties for a sign-off, and update notified field"""
        verbosity = options['verbosity']

        # Get the current time
        now = datetime.datetime.utcnow().replace(tzinfo=utc)

        # Get a decent text representation of the signer
        signed_by = signoff.signed_by.first_name + ' ' + signoff.signed_by.last_name

        # Now, make a list of user objects to write to
        email_targets = list()

        for target in signoff.assessment_state.get_notify_list():
            # Is it a Module Coordinator
            if target == signoff.assessment_state.COORDINATOR:
                if signoff.module.coordinator:
                    email_targets.append(signoff.module.coordinator.user)
            # Or a moderator
            if target == signoff.assessment_state.MODERATOR:
                for moderator in signoff.module.moderators.all():
                    email_targets.append(moderator.user)
            # Or a member of staff allocated to the module
            if target == signoff.assessment_state.TEAM_MEMBER:
                for module_staff in ModuleStaff.objects.all().filter(module=signoff.module):
                    email_targets.append(module_staff.staff.user)
            # Or an external examiner
            if target == signoff.assessment_state.EXTERNAL:
                for external in signoff.module.lead_programme.examiners.all():
                    email_targets.append(external.user)
            # Or a member of assessment staff
            if target == signoff.assessment_state.ASSESSMENT_STAFF:
                for staff in AssessmentStaff.objects.all().filter(package=signoff.module.package):
                    email_targets.append(staff.user)

        email_addresses = list()
        separator = ', '

        for target in email_targets:
            email_addresses.append("{} {} <{}>".format(target.first_name, target.last_name, target.email))

        # Get the whole assessment history
        assessment_history = signoff.module.get_assessment_history()

        # Trim off any sign-offs before the current one (in case more happened before this job)
        corrected_history = list()
        for (item, item_resources) in assessment_history:
            if item and (item.created <= signoff.created):
                corrected_history.append((item, item_resources))

        if verbosity:
            self.stdout.write('Update {} for {}'.format(signoff.assessment_state, signoff.module))
            self.stdout.write('  Signed on {} by {}'.format(signoff.created, signed_by))

            if not len(email_addresses):
                self.stdout.write(self.style.WARNING('  Nobody meets criteria for notification.'))
            if verbosity > 2:
                for address in email_addresses:
                    self.stdout.write(self.style.SUCCESS('  Notify: {}'.format(address)))

        # If there's nobody to write to, bail out
        if not len(email_addresses):
            # Nobody to talk to!
            if not options['test-only']:
                # Remember that we would have sent the notifications
                signoff.notified = now
                signoff.save()
            return False

        plaintext = get_template('loads/emails/assessment_updates.txt')
        html = get_template('loads/emails/assessment_updates.html')

        context_dict = {
            'signoff': signoff,
            'assessment_history': corrected_history,
            'base_url': settings.WAM_URL,
        }

        email_subject = 'Assessment Sign-off update for {}'.format(signoff.module)

        from_email, to = settings.WAM_AUTO_EMAIL_FROM, separator.join(email_addresses)
        text_content = plaintext.render(context_dict)
        html_content = html.render(context_dict)

        email = EmailMultiAlternatives(email_subject, text_content, from_email, [to])
        email.attach_alternative(html_content, "text/html")

        if not options['test-only']:
            email.send()
            # Remember that we sent the notifications
            signoff.notified = now
            signoff.save()
        return True
