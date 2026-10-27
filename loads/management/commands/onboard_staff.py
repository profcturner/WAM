"""A custom command to create WAM accounts for a School's staff from a directory, before they log in"""
import logging

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from loads.directory import get_directory_source, find_user, onboard_staff_record

# Get an instance of a logger
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = ("Create or update WAM users and staff for everyone in a School, "
            "using the directory source configured in WAM_DIRECTORY_SOURCE")

    def add_arguments(self, parser):
        parser.add_argument('school',
                            help="The School as the directory names it, e.g. 'School of Computing'")
        parser.add_argument('--dry-run',
                            action='store_true',
                            help="List who would be onboarded, without changing anything")
        parser.add_argument('--no-externals',
                            action='store_true',
                            help="Skip anyone the directory source marks as external")

    def handle(self, *args, **options):
        school = options['school']
        dry_run = options['dry_run']
        prefix = '[dry-run] ' if dry_run else ''

        try:
            source = get_directory_source()
            records = list(source.staff_in_school(school))
        except ImproperlyConfigured as e:
            raise CommandError(str(e))

        created = updated = skipped = 0

        for record in records:
            username = record.get('username')
            if not username:
                self.stderr.write(f"Skipping a record with no username: {record}")
                skipped += 1
                continue

            if options['no_externals'] and record.get('is_external'):
                skipped += 1
                continue

            exists = find_user(username) is not None
            kind = 'external' if record.get('is_external') else 'staff'
            self.stdout.write(f"{prefix}{'update' if exists else 'create'} {kind:8} {username:20} "
                              f"{record.get('first_name') or ''} {record.get('last_name') or ''}")

            if dry_run:
                continue

            staff, was_created = onboard_staff_record(record)
            if was_created:
                created += 1
            else:
                updated += 1

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"{prefix}{len(records) - skipped} to onboard, {skipped} skipped"))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Done: {created} created, {updated} updated, {skipped} skipped"))
