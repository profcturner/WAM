from django import forms
from django.utils.html import format_html, mark_safe

# Contains some custom widgets to make handling more intuitive

# Semester Widget - handles comma separated 1,2,3 semesters more intuitively

class SemesterWidget(forms.Widget):
    """
    Renders a row of labelled checkboxes for semesters 1–3.
    Reads/writes the comma-separated integer string used by the model field,
    e.g. "1", "2,3", "1,2,3".
    """

    SEMESTERS = [1, 2, 3]

    def __init__(self, attrs=None, semester_labels=None):
        super().__init__(attrs)
        # Allow callers to override the labels, e.g. {1: "Autumn", 2: "Spring", 3: "Summer"}
        self.semester_labels = semester_labels or {s: f"Semester {s}" for s in self.SEMESTERS}

    def _parse_value(self, value):
        """Return a set of ints from a comma-separated string or list."""
        if not value:
            return set()
        if isinstance(value, (list, tuple)):
            return {int(v) for v in value if str(v).strip().isdigit()}
        return {int(v.strip()) for v in str(value).split(',') if v.strip().isdigit()}

    def value_from_datadict(self, data, files, name):
        """Collect checked boxes and return a comma-separated string."""
        selected = [
            str(s) for s in self.SEMESTERS
            if data.get(f"{name}_{s}")
        ]
        return ','.join(selected)

    def render(self, name, value, attrs=None, **kwargs):
        checked = self._parse_value(value)
        final_attrs = self.build_attrs(attrs or {})
        widget_id = final_attrs.get('id', name)

        checkboxes = []
        for semester in self.SEMESTERS:
            checkbox_id = f"{widget_id}_{semester}"
            input_name = f"{name}_{semester}"
            is_checked = 'checked' if semester in checked else ''
            label = self.semester_labels.get(semester, f"Semester {semester}")
            checkboxes.append(format_html(
                '<label class="semester-option" for="{id}">'
                '  <input type="checkbox" name="{name}" id="{id}" value="{val}" {checked}>'
                '  {label}'
                '</label>',
                id=checkbox_id,
                name=input_name,
                val=semester,
                checked=mark_safe(is_checked),
                label=label,
            ))

        inner = mark_safe('\n'.join(checkboxes))
        return format_html('<div class="semester-widget">{}</div>', inner)

    class Media:
        css = {'all': ('widgets/semester_widget.css',)}


class SemesterField(forms.CharField):
    """
    Form field that pairs with SemesterWidget.
    Validates that the result is a non-empty comma-separated list of
    integers in the range 1–3.
    """

    VALID_SEMESTERS = {1, 2, 3}

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', SemesterWidget())  # instance, not class
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)  # handles required check on the raw string
        if not value:
            if self.required:
                raise forms.ValidationError("Please select at least one semester.")
            return value
        try:
            parts = {int(v.strip()) for v in value.split(',') if v.strip()}
        except ValueError:
            raise forms.ValidationError("Invalid semester data.")
        invalid = parts - self.VALID_SEMESTERS
        if invalid:
            raise forms.ValidationError(f"Invalid semester values: {invalid}")
        # Return in canonical ascending order
        return ','.join(str(s) for s in sorted(parts))


# ---------------------------------------------------------------------------
# Hours / Percentage Toggle Widget
# ---------------------------------------------------------------------------

class HoursPercentageWidget(forms.MultiWidget):
    """
    A compound widget spanning three model fields:
      - hours_percentage  ('H' or 'P')
      - hours             (positive integer, shown when H is selected)
      - percentage        (positive integer, shown when P is selected)

    The three sub-widgets are rendered together with JS that hides the
    irrelevant numeric input as the toggle changes.
    """

    def __init__(self, attrs=None):
        widgets = [
            forms.RadioSelect(
                choices=[('H', 'Hours'), ('P', 'Percentage')],
                attrs={'class': 'hp-toggle'},
            ),
            forms.NumberInput(attrs={'class': 'hp-hours', 'min': 0}),
            forms.NumberInput(attrs={'class': 'hp-percentage', 'min': 0, 'max': 100}),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        """
        value here is the tuple (hours_percentage, hours, percentage)
        assembled by HoursPercentageField from the form's initial data.
        """
        if value:
            return list(value)
        return ['H', None, None]

    def render(self, name, value, attrs=None, **kwargs):
        rendered = super().render(name, value, attrs, **kwargs)
        return format_html(
            '<div class="hours-percentage-widget" data-name="{}">{}</div>',
            name,
            mark_safe(rendered),
        )

    class Media:
        css = {'all': ('widgets/hours_percentage_widget.css',)}
        js = ('widgets/hours_percentage_widget.js',)


class HoursPercentageField(forms.MultiValueField):
    """
    A MultiValueField that combines hours_percentage, hours, and percentage
    into a single form field backed by HoursPercentageWidget.

    Usage in a ModelForm:

        class ActivityForm(forms.ModelForm):
            hours_percentage_combined = HoursPercentageField()

            class Meta:
                model = Activity
                exclude = ['hours', 'percentage', 'hours_percentage']

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                instance = kwargs.get('instance')
                if instance:
                    self.fields['hours_percentage_combined'].initial = (
                        instance.hours_percentage,
                        instance.hours,
                        instance.percentage,
                    )

            def save(self, commit=True):
                instance = super().save(commit=False)
                combined = self.cleaned_data['hours_percentage_combined']
                instance.hours_percentage = combined['hours_percentage']
                instance.hours = combined['hours']
                instance.percentage = combined['percentage']
                if commit:
                    instance.save()
                return instance
    """

    def __init__(self, *args, **kwargs):
        fields = [
            forms.ChoiceField(choices=[('H', 'Hours'), ('P', 'Percentage')]),
            forms.IntegerField(min_value=0, required=False),
            forms.IntegerField(min_value=0, max_value=100, required=False),
        ]
        kwargs.setdefault('widget', HoursPercentageWidget())
        kwargs.setdefault('require_all_fields', False)
        super().__init__(fields=fields, *args, **kwargs)

    def compress(self, data_list):
        """
        Called with [hours_percentage, hours, percentage].
        Returns a dict so the form's save() can unpack each value by name.
        """
        if not data_list:
            return {}

        hp = data_list[0] if len(data_list) > 0 else 'H'
        hours = data_list[1] if len(data_list) > 1 else None
        percentage = data_list[2] if len(data_list) > 2 else None

        if hp == 'H' and (hours is None or hours == ''):
            raise forms.ValidationError("Please enter a number of hours.")
        if hp == 'P' and (percentage is None or percentage == ''):
            raise forms.ValidationError("Please enter a percentage.")

        return {
            'hours_percentage': hp,
            'hours': hours if hours is not None else 0,
            'percentage': percentage if percentage is not None else 0,
        }
