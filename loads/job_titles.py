"""
A best guess, from someone's job title, at what kind of staff they are, for when the directory has
nothing better (Entra / AD rarely says whether someone is academic).

There are four outcomes:

    academic    lecturers, readers, professors, teaching fellows, heads of School, deans...
                suggested for the School's "Academic Staff" group, with a workload
    research    research fellows, associates and assistants. Not academic: they don't share the
                academic peer group's norms. No group is suggested, and whether they have a
                workload is decided for each person
    other       administrative and technical staff: suggested for the School's "Admin Staff" group,
                with no workload
    None        unknown: nothing is suggested, and someone decides

Titles are matched against phrases for each kind (WAM_JOB_TITLE_PATTERNS), as whole words, ignoring
case and punctuation. When phrases of more than one kind match, the longest phrase wins, so
"Lecturer Support Officer" is admin ("support officer") but "Assistant Professor" is academic
("assistant professor"); a tie between kinds is unknown. To change a result, add a longer phrase.
Words after a matched phrase and "in", "of" or "for" are a subject, and ignored: "Lecturer in Business
Administration" is academic.

Suggestions are only ever suggestions: local admins review them on the School groups page, and
onboarding applies them only to people it has just created.
"""
import re

from django.conf import settings
from django.contrib.auth.models import Group

ACADEMIC = 'academic'
RESEARCH = 'research'
OTHER = 'other'

LABELS = {
    ACADEMIC: "Academic",
    RESEARCH: "Research",
    OTHER: "Admin or technical",
    None: "Unknown",
}

DEFAULT_PATTERNS = {
    ACADEMIC: [
        'lecturer', 'reader', 'professor', 'assistant professor', 'associate professor', 'emeritus professor',
        'teaching fellow', 'head of school', 'deputy head of school', 'associate head of school',
        'head of department', 'dean', 'associate dean', 'course director',
    ],
    RESEARCH: [
        'research fellow', 'research associate', 'research assistant', 'research officer', 'researcher',
        'postdoctoral', 'post doctoral', 'postdoc',
    ],
    OTHER: [
        'administrator', 'administrative', 'administration', 'admin', 'officer', 'support officer',
        'technician', 'technical', 'manager', 'clerk', 'secretary', 'receptionist', 'coordinator',
        'co ordinator', 'assistant', 'adviser', 'advisor', 'executive', 'personal assistant',
    ],
}


def patterns():
    """The phrases for each kind, from WAM_JOB_TITLE_PATTERNS, or the defaults"""
    return getattr(settings, 'WAM_JOB_TITLE_PATTERNS', None) or DEFAULT_PATTERNS


def normalise(text):
    """Lower case words, with punctuation as spaces: "Co-ordinator (Labs)" is "co ordinator labs" """
    return ' '.join(re.sub(r"[^\w]+", ' ', (text or '').lower()).split())


def classify(job_title, phrases=None):
    """
    (kind, phrase): the kind of staff a job title suggests (ACADEMIC, RESEARCH, OTHER or None),
    and the phrase that decided it (None if nothing did, or kinds tied).
    """
    title = normalise(job_title)
    if not title:
        return None, None
    matches = []  # (kind, phrase, start, end)
    for kind, kind_phrases in (phrases or patterns()).items():
        for phrase in kind_phrases:
            phrase = normalise(phrase)
            if phrase:
                for found in re.finditer(r'\b' + re.escape(phrase) + r'\b', title):
                    matches.append((kind, phrase, found.start(), found.end()))
    # A role followed by "in", "of" or "for" names a subject or a place, which says nothing about the role:
    # "Lecturer in Business Administration", "Professor of Health Management", "Head of School of Nursing"
    subject_starts = [end for kind, phrase, start, end in matches if re.match(r' (in|of|for) ', title[end:])]
    if subject_starts:
        cut = min(subject_starts)
        matches = [match for match in matches if match[3] <= cut]
    best = {}
    for kind, phrase, start, end in matches:
        if len(phrase) > len(best.get(kind, '')):
            best[kind] = phrase
    if not best:
        return None, None
    longest = max(len(phrase) for phrase in best.values())
    winners = [kind for kind, phrase in best.items() if len(phrase) == longest]
    if len(winners) > 1:
        return None, None
    return winners[0], best[winners[0]]


def school_subgroups(school):
    """The School's (Academic Staff, Admin Staff) groups, where they exist"""
    if school is None:
        return None, None
    names = {f"{school.name} Academic Staff": 0, f"{school.name} Admin Staff": 1}
    found = [None, None]
    for group in Group.objects.filter(name__in=names):
        found[names[group.name]] = group
    return tuple(found)


class Suggestion:
    """
    What someone's job title suggests for them: a kind, a School subgroup (or None) and whether they
    have a workload (or None: no suggestion)
    """

    def __init__(self, staff, subgroups=None, phrases=None):
        self.staff = staff
        self.kind, self.phrase = classify(staff.job_title, phrases)
        self.label = LABELS[self.kind]
        academic_group, admin_group = subgroups if subgroups is not None else school_subgroups(staff.school)
        self.subgroups = (academic_group, admin_group)
        self.group = {ACADEMIC: academic_group, OTHER: admin_group}.get(self.kind)
        self.has_workload = {ACADEMIC: True, OTHER: False}.get(self.kind)

    def __bool__(self):
        return self.kind is not None


def apply_suggestion(staff, new=False, subgroups=None):
    """
    Apply someone's suggestion: add them to the suggested School subgroup and set whether they have a
    workload, but only if they're in neither subgroup yet, so a decision someone has made isn't undone.
    For new people (just onboarded), research staff start with no workload, to be turned on for each
    person who needs it.

    Returns a list of what changed, as strings.
    """
    if staff.is_external:
        return []
    suggestion = Suggestion(staff, subgroups=subgroups)
    current = set(staff.user.groups.values_list('pk', flat=True))
    if any(group is not None and group.pk in current for group in suggestion.subgroups):
        return []
    changes = []
    if suggestion.group is not None:
        staff.user.groups.add(suggestion.group)
        changes.append(f"added to {suggestion.group.name}")
    has_workload = suggestion.has_workload
    if has_workload is None and new and suggestion.kind == RESEARCH:
        has_workload = False
    if has_workload is not None and staff.has_workload != has_workload:
        staff.has_workload = has_workload
        staff.save(update_fields=['has_workload'])
        changes.append("has workload" if has_workload else "no workload")
    return changes
