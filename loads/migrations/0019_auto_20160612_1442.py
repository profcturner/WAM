# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0018_modulestaff_package'),
    ]

    operations = [
        migrations.AddField(
            model_name='workpackage',
            name='contact_admin_scaling',
            field=models.DecimalField(default=1, max_digits=5, decimal_places=2),
        ),
        migrations.AddField(
            model_name='workpackage',
            name='contact_assessment_scaling',
            field=models.DecimalField(default=1, max_digits=5, decimal_places=2),
        ),
        migrations.AddField(
            model_name='workpackage',
            name='credit_contact_scaling',
            field=models.DecimalField(default=0.4, max_digits=5, decimal_places=2),
        ),
        migrations.AddField(
            model_name='workpackage',
            name='nominal_hours',
            field=models.PositiveIntegerField(default=1600),
        ),
    ]
