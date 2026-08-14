"""
Migration: add number_students to Module, populated by parsing ModuleSize.text.

Handles two formats observed in production data:
  "0-10", "11-20", "21-50", "51-100", "101-200"  →  midpoint of range
  "200+"                                           →  lower bound (200)

If an unrecognised format is encountered the migration fails loudly with
the offending text, rather than silently producing a wrong value.
"""

import re
from django.db import migrations, models


# Matches "0-10", "11-20", "101-200" etc.
RE_RANGE = re.compile(r'^(\d+)\s*-\s*(\d+)$')
# Matches "200+" etc.
RE_OPEN  = re.compile(r'^(\d+)\+$')





def midpoint_from_text(text):
    """
    Parse a ModuleSize.text value and return a representative integer
    student count.

    Raises ValueError for unrecognised formats so the migration fails
    clearly rather than silently producing bad data.
    """
    text = text.strip()

    m = RE_RANGE.match(text)
    if m:
        low, high = int(m.group(1)), int(m.group(2))
        return round((low + high) / 2)

    m = RE_OPEN.match(text)
    if m:
        # Open-ended bin: use the lower bound as a conservative estimate.
        # Change to e.g. int(m.group(1)) + 50 if a higher estimate is preferred.
        return int(m.group(1))

    raise ValueError(
        f"ModuleSize text '{text}' does not match any recognised format "
        f"('N-M' or 'N+'). Update the migration or fix the data before running."
    )


def populate_number_students(apps, schema_editor):
    Module = apps.get_model('loads', 'Module')
    ModuleSize = apps.get_model('loads', 'ModuleSize')

    # Pre-build a lookup so we only parse each ModuleSize once
    size_map = {
        size.pk: midpoint_from_text(size.text)
        for size in ModuleSize.objects.all()
    }

    modules_to_update = []
    for module in Module.objects.all():
        module.number_students = size_map[module.size_id]
        modules_to_update.append(module)

    Module.objects.bulk_update(modules_to_update, ['number_students'], batch_size=200)


def reverse_populate(apps, schema_editor):
    Module = apps.get_model('loads', 'Module')
    Module.objects.all().update(number_students=None)


class Migration(migrations.Migration):

    # Replace with your actual most recent migration name
    dependencies = [
        ('loads', '0054_module_coordinator_hours_workpackage_admin_formula_and_more'),
    ]

    operations = [
        # Step 1: add nullable so existing rows are valid immediately
        migrations.AddField(
            model_name='module',
            name='number_students',
            field=models.PositiveSmallIntegerField(
                null=True,
                blank=True,
                help_text='Number of students enrolled. Replaces the size category field.',
            ),
        ),

        # Step 2: populate from parsed ModuleSize.text midpoints
        migrations.RunPython(
            populate_number_students,
            reverse_code=reverse_populate,
        ),

        # Step 3: make non-nullable now every row has a value
        migrations.AlterField(
            model_name='module',
            name='number_students',
            field=models.PositiveSmallIntegerField(
                help_text='Number of students enrolled. Replaces the size category field.',
            ),
        ),
    ]