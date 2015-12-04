# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0012_auto_20151130_1311'),
    ]

    operations = [
        migrations.AddField(
            model_name='modulestaff',
            name='academic_year',
            field=models.CharField(default='2015/2016', max_length=10),
        ),
        migrations.AlterField(
            model_name='module',
            name='contact_hours',
            field=models.PositiveSmallIntegerField(blank=True),
        ),
    ]
