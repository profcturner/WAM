# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0028_auto_20160706_2224'),
    ]

    operations = [
        migrations.AlterField(
            model_name='module',
            name='admin_hours',
            field=models.PositiveSmallIntegerField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='module',
            name='assessment_hours',
            field=models.PositiveSmallIntegerField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='module',
            name='contact_hours',
            field=models.PositiveSmallIntegerField(null=True, blank=True),
        ),
    ]
