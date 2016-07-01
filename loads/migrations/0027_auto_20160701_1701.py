# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0026_auto_20160629_1009'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='activitygenerator',
            name='activity_set',
        ),
        migrations.RemoveField(
            model_name='project',
            name='activity_set',
        ),
        migrations.AddField(
            model_name='activityset',
            name='generator',
            field=models.ForeignKey(blank=True, null=True, to='loads.ActivityGenerator'),
        ),
        migrations.AddField(
            model_name='activityset',
            name='project',
            field=models.ForeignKey(blank=True, null=True, to='loads.Project'),
        ),
    ]
