"""
Check what job titles suggest about staff (see loads.job_titles), and optionally apply it.

Lists every distinct job title among internal staff, with how many people have it and what it's
taken to mean, so the phrases (WAM_JOB_TITLE_PATTERNS) can be tuned before anyone relies on them.
Unknown titles are listed last.

With --apply, each person in neither of their School's Academic and Admin Staff groups yet is added
to the suggested one, and their workload set to match (research staff and unknowns are left alone).
Anyone already in either group is skipped, so decisions already made stand. Try it without --apply first.
"""
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

from loads.job_titles import LABELS, apply_suggestion, classify, school_subgroups
from loads.models import School, Staff


class Command(BaseCommand):
    help = "List job titles and what they suggest about staff; with --apply, set groups and workloads from them"

    def add_arguments(self, parser):
        parser.add_argument('--school', help="Only staff in this School (its name)")
        parser.add_argument('--apply', action='store_true',
                            help="Add people to the suggested School subgroup and set their workload, where "
                                 "they're in neither subgroup yet")

    def handle(self, *args, **options):
        staff = Staff.objects.filter(is_external=False, user__is_active=True).select_related('user', 'school')
        if options['school']:
            school = School.objects.filter(name=options['school']).first()
            if school is None:
                self.stderr.write(f"No School called \"{options['school']}\"")
                return
            staff = staff.filter(school=school)

        titles = Counter((person.job_title or '').strip() for person in staff)
        by_kind = defaultdict(list)
        for title, count in titles.items():
            kind, phrase = classify(title)
            by_kind[kind].append((title, count, phrase))

        for kind in ('academic', 'research', 'other', None):
            entries = sorted(by_kind.get(kind, []), key=lambda entry: (-entry[1], entry[0]))
            people = sum(count for _, count, _ in entries)
            self.stdout.write(self.style.MIGRATE_HEADING(f"{LABELS[kind]}: {people} people, {len(entries)} titles"))
            for title, count, phrase in entries:
                because = f'  ("{phrase}")' if phrase else ''
                self.stdout.write(f"  {count:5}  {title or '(no job title)'}{because}")
            self.stdout.write("")

        if not options['apply']:
            self.stdout.write("Nothing changed. Run with --apply to set groups and workloads from these.")
            return

        changed = skipped = 0
        subgroups_by_school = {}
        for person in staff:
            if person.school_id not in subgroups_by_school:
                subgroups_by_school[person.school_id] = school_subgroups(person.school)
            changes = apply_suggestion(person, subgroups=subgroups_by_school[person.school_id])
            if changes:
                changed += 1
                self.stdout.write(f"  {person} ({person.user.username}): {', '.join(changes)}")
            else:
                skipped += 1
        self.stdout.write(self.style.SUCCESS(f"Changed {changed} people; {skipped} left as they were."))
