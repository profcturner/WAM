# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0006_courseworktracker_examtracker_loadtracking'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activity',
            name='staff',
            field=models.ForeignKey(to='loads.Staff', null=True, blank=True),
        ),
    ]
