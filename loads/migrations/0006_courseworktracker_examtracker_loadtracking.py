# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0005_auto_20151017_1334'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseworkTracker',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('academic_year', models.CharField(max_length=10, default='2015/2016')),
                ('progress', models.CharField(choices=[('SET', 'Coursework Set'), ('MODERATE', 'Internal Moderation'), ('EXTERNAL', 'Sent to External Examiner'), ('REWORK', 'Reworked'), ('EXAMOFFICE', 'Submitted to Exams Office')], max_length=15, default='SET')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('module', models.ForeignKey(to='loads.Module')),
            ],
        ),
        migrations.CreateModel(
            name='ExamTracker',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('academic_year', models.CharField(max_length=10, default='2015/2016')),
                ('progress', models.CharField(choices=[('SET', 'Exam Set'), ('MODERATE', 'Internal Moderation'), ('EXTERNAL', 'Sent to External Examiner'), ('REWORK', 'Reworked'), ('EXAMOFFICE', 'Submitted to Exams Office')], max_length=15, default='SET')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('module', models.ForeignKey(to='loads.Module')),
            ],
        ),
        migrations.CreateModel(
            name='LoadTracking',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('academic_year', models.CharField(max_length=10, default='2015/2016')),
                ('semester1_hours', models.DecimalField(max_digits=15, decimal_places=2)),
                ('semester2_hours', models.DecimalField(max_digits=15, decimal_places=2)),
                ('semester3_hours', models.DecimalField(max_digits=15, decimal_places=2)),
                ('total_hours', models.DecimalField(max_digits=15, decimal_places=2)),
                ('mean', models.DecimalField(max_digits=15, decimal_places=2)),
                ('sd', models.DecimalField(max_digits=15, decimal_places=2)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
