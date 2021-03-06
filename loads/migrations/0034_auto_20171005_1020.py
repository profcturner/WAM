# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-10-05 10:20
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import re


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0033_auto_20170724_1512'),
    ]

    operations = [
        migrations.AddField(
            model_name='module',
            name='programmes',
            field=models.ManyToManyField(blank=True, related_name='modules', to='loads.Programme'),
        ),
        migrations.AlterField(
            model_name='activity',
            name='semester',
            field=models.CharField(max_length=10, validators=[django.core.validators.RegexValidator(re.compile('^\\d+(?:\\,\\d+)*\\Z', 32), code='invalid', message='Enter only digits separated by commas.')]),
        ),
        migrations.AlterField(
            model_name='activitygenerator',
            name='semester',
            field=models.CharField(max_length=10, validators=[django.core.validators.RegexValidator(re.compile('^\\d+(?:\\,\\d+)*\\Z', 32), code='invalid', message='Enter only digits separated by commas.')]),
        ),
        migrations.AlterField(
            model_name='module',
            name='lead_programme',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='lead_modules', to='loads.Programme'),
        ),
        migrations.AlterField(
            model_name='module',
            name='semester',
            field=models.CharField(max_length=10, validators=[django.core.validators.RegexValidator(re.compile('^\\d+(?:\\,\\d+)*\\Z', 32), code='invalid', message='Enter only digits separated by commas.')]),
        ),
    ]
