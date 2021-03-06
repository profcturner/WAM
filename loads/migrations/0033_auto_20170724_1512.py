# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-07-24 15:12
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0032_assessmentresource_owner'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssessmentStaff',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('package', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='loads.WorkPackage')),
                ('staff', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='loads.Staff')),
            ],
        ),
        migrations.AlterField(
            model_name='courseworktracker',
            name='academic_year',
            field=models.CharField(default='2016/2017', max_length=10),
        ),
        migrations.AlterField(
            model_name='examtracker',
            name='academic_year',
            field=models.CharField(default='2016/2017', max_length=10),
        ),
        migrations.AlterField(
            model_name='loadtracking',
            name='academic_year',
            field=models.CharField(default='2016/2017', max_length=10),
        ),
    ]
