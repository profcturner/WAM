# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0024_auto_20160627_1049'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='body',
            options={'verbose_name_plural': 'bodies'},
        ),
        migrations.AlterModelOptions(
            name='projectstaff',
            options={'verbose_name_plural': 'project staff'},
        ),
        migrations.AddField(
            model_name='workpackage',
            name='days_in_week',
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.AddField(
            model_name='workpackage',
            name='working_days',
            field=models.PositiveIntegerField(default=228),
        ),
        migrations.AlterField(
            model_name='activitygenerator',
            name='activity_set',
            field=models.ForeignKey(to='loads.ActivitySet', blank=True, on_delete=django.db.models.deletion.SET_NULL, null=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='activity_set',
            field=models.ForeignKey(to='loads.ActivitySet', blank=True, on_delete=django.db.models.deletion.SET_NULL, null=True),
        ),
    ]
