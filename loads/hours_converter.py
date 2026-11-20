"""
Enter a module's workload as hours per person, and turn it into what WAM stores.

WAM keeps a module's contact, assessment and admin hours as totals on the module, and each
person's share as a percentage of each, to two decimal places (ModuleStaff). Some admin staff have the
figures the other way round: hours per person. This converts them:

  - each column's total becomes the module's (fixed) total for that category, to a tenth of an
    hour, as the module stores them;
  - each person's percentage is their share of the total, to two decimal places, rounded so that
    each column still adds up to exactly 100 (largest remainder), or 0 throughout for a column with no hours.

Rounding means the hours WAM then works out for someone can differ slightly from what was
entered, so the plan records both, for the preview.

Coordinator hours are separate and left alone.
"""
import hashlib
from decimal import ROUND_HALF_UP, Decimal

from django import forms
from fancy_formset import FancyFormSet

CATEGORIES = (
    ('contact', "Contact hours"),
    ('assessment', "Assessment hours"),
    ('admin', "Admin hours"),
)


def tenths(value):
    """Round to a tenth of an hour, as modules store their hours; halves up, as people expect"""
    return Decimal(value).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


def percentages(hours):
    """
    Each value's share of the total, as a percentage to two decimal places, adding up to exactly 100
    (or all 0 if the total is 0). The largest remainders get the spare hundredths; ties go to the earlier entry.
    """
    total = sum(hours)
    if not total:
        return [Decimal(0) for _ in hours]
    # Work in hundredths of a percent, so 10000 is the whole
    exact = [Decimal(h) * 10000 / Decimal(total) for h in hours]
    shares = [int(e) for e in exact]
    spare = 10000 - sum(shares)
    by_remainder = sorted(range(len(hours)), key=lambda i: (-(exact[i] - shares[i]), i))
    for i in by_remainder[:spare]:
        shares[i] += 1
    return [Decimal(share) / 100 for share in shares]


class Plan:
    """
    What saving the entered hours would do: the module's new totals, and each person's new
    percentages and the hours those give.

    rows    a list of (staff, {category: entered hours}) for each person, in order
    """

    def __init__(self, module, rows):
        self.module = module
        # People with no hours at all are left off: they won't have an allocation
        self.rows = [(staff, entered) for staff, entered in rows if any(entered.values())]
        self.dropped = [staff for staff, entered in rows if not any(entered.values())]

        self.entered_totals = {key: sum((entered[key] for _, entered in self.rows), Decimal(0))
                               for key, _ in CATEGORIES}
        self.totals = {key: tenths(total) for key, total in self.entered_totals.items()}
        shares = {key: percentages([entered[key] for _, entered in self.rows]) for key, _ in CATEGORIES}

        self.people = []
        for index, (staff, entered) in enumerate(self.rows):
            person = {'staff': staff, 'categories': []}
            for key, label in CATEGORIES:
                share = shares[key][index]
                hours = self.totals[key] * share / 100
                person[key] = share
                person['categories'].append({
                    'key': key,
                    'entered': entered[key],
                    'percentage': share,
                    'hours': hours,
                    # Within a twentieth of an hour shows as the same, to one decimal place
                    'differs': abs(hours - entered[key]) >= Decimal('0.05'),
                })
            self.people.append(person)

        # What's there now, to compare against
        self.current_totals = {
            'contact': (module.contact_hours, module.get_contact_hours()),
            'assessment': (module.assessment_hours, module.get_assessment_hours()),
            'admin': (module.admin_hours, module.get_admin_hours()),
        }

    @property
    def rounded(self):
        """Whether any total or anyone's hours differ from what was entered"""
        if any(self.totals[key] != self.entered_totals[key] for key, _ in CATEGORIES):
            return True
        return any(c['differs'] for person in self.people for c in person['categories'])

    def total_rows(self):
        """(label, current fixed value or None, current value, new total, entered total) per category"""
        return [(label, self.current_totals[key][0], self.current_totals[key][1], self.totals[key],
                 self.entered_totals[key]) for key, label in CATEGORIES]

    def fingerprint(self):
        """Identifies these figures, so a confirmation can be checked against what was previewed"""
        parts = [str(self.module.pk)]
        for person in self.people:
            parts.append(str(person['staff'].pk))
            parts.extend(str(c['entered']) for c in person['categories'])
        return hashlib.sha256('|'.join(parts).encode()).hexdigest()[:16]


class PersonHoursForm(forms.Form):
    """One person's hours on a module"""
    staff = forms.ModelChoiceField(queryset=None, label="Staff member")
    contact = forms.DecimalField(label="Contact hours", min_value=0, max_digits=6, decimal_places=1,
                                 required=False, initial=0)
    assessment = forms.DecimalField(label="Assessment hours", min_value=0, max_digits=6, decimal_places=1,
                                    required=False, initial=0)
    admin = forms.DecimalField(label="Admin hours", min_value=0, max_digits=6, decimal_places=1,
                               required=False, initial=0)

    def __init__(self, *args, staff_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['staff'].queryset = staff_queryset
        for key, _ in CATEGORIES:
            self.fields[key].widget.attrs.update({'step': '0.5', 'class': 'form-control'})
        self.fields['staff'].widget.attrs.update({'class': 'form-select'})

    def clean(self):
        cleaned = super().clean()
        for key, _ in CATEGORIES:
            if cleaned.get(key) is None:
                cleaned[key] = Decimal(0)
        return cleaned


class BasePersonHoursFormSet(FancyFormSet):
    """Everyone's hours on a module: each person once, and at least someone with some hours"""

    def clean(self):
        if any(self.errors):
            return
        seen = set()
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            staff = form.cleaned_data.get('staff')
            if staff is None:
                continue
            if staff in seen:
                raise forms.ValidationError(f"{staff} is listed more than once.", code='duplicate')
            seen.add(staff)
        if not any(any(form.cleaned_data.get(key) for key, _ in CATEGORIES) for form in self.kept_forms()):
            raise forms.ValidationError("Enter some hours for at least one person.", code='empty')

    def kept_forms(self):
        """The forms with a person in, that aren't being deleted"""
        return [form for form in self.forms
                if form.cleaned_data.get('staff') and not (self.can_delete and self._should_delete_form(form))]

    def rows(self):
        return [(form.cleaned_data['staff'], {key: form.cleaned_data[key] for key, _ in CATEGORIES})
                for form in self.kept_forms()]


PersonHoursFormSet = forms.formset_factory(PersonHoursForm, formset=BasePersonHoursFormSet,
                                           extra=1, can_delete=True)
