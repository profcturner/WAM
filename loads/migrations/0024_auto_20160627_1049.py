# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0006_require_contenttypes_0002'),
        ('loads', '0023_auto_20160615_0006'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityGenerator',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=300)),
                ('hours', models.PositiveSmallIntegerField()),
                ('percentage', models.PositiveSmallIntegerField()),
                ('hours_percentage', models.CharField(default='H', choices=[('H', 'Hours'), ('P', 'Percentage')], max_length=1)),
                ('semester', models.CommaSeparatedIntegerField(max_length=10)),
                ('comment', models.CharField(default='', max_length=200, blank=True)),
                ('details', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='ActivitySet',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=300)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Body',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=300)),
                ('details', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=300)),
                ('start', models.DateField()),
                ('end', models.DateField()),
                ('activity_set', models.ForeignKey(null=True, to='loads.ActivitySet', blank=True)),
                ('activity_type', models.ForeignKey(to='loads.ActivityType')),
                ('body', models.ForeignKey(to='loads.Body')),
            ],
        ),
        migrations.CreateModel(
            name='ProjectStaff',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('start', models.DateField()),
                ('end', models.DateField()),
                ('hours_per_week', models.FloatField()),
                ('project', models.ForeignKey(to='loads.Project')),
                ('staff', models.ForeignKey(to='loads.Staff')),
            ],
        ),
        migrations.AddField(
            model_name='activitygenerator',
            name='activity_set',
            field=models.ForeignKey(null=True, to='loads.ActivitySet', blank=True),
        ),
        migrations.AddField(
            model_name='activitygenerator',
            name='activity_type',
            field=models.ForeignKey(to='loads.ActivityType'),
        ),
        migrations.AddField(
            model_name='activitygenerator',
            name='groups',
            field=models.ManyToManyField(to='auth.Group', blank=True),
        ),
        migrations.AddField(
            model_name='activitygenerator',
            name='module',
            field=models.ForeignKey(null=True, to='loads.Module', blank=True),
        ),
        migrations.AddField(
            model_name='activitygenerator',
            name='package',
            field=models.ForeignKey(to='loads.WorkPackage'),
        ),
        migrations.AddField(
            model_name='activitygenerator',
            name='targets',
            field=models.ManyToManyField(to='loads.Staff', blank=True),
        ),
        migrations.AddField(
            model_name='activity',
            name='activity_set',
            field=models.ForeignKey(null=True, to='loads.ActivitySet', blank=True),
        ),
    ]
