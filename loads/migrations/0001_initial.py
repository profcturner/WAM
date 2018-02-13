# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('hours', models.PositiveSmallIntegerField()),
                ('percentage', models.PositiveSmallIntegerField()),
                ('hours_percentage', models.CharField(max_length=1, choices=[('H', 'Hours'), ('P', 'Percentage')], default='H')),
                ('semester', models.CommaSeparatedIntegerField(max_length=10)),
                ('comment', models.CharField(max_length=200, default='')),
                ('academic_year', models.CharField(max_length=10, default='2015/2016')),
            ],
            options={
                'verbose_name_plural': 'activities',
            },
        ),
        migrations.CreateModel(
            name='ActivityType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='Module',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, primary_key=True, serialize=False)),
                ('module_code', models.CharField(max_length=10)),
                ('module_name', models.CharField(max_length=200)),
                ('semester', models.CommaSeparatedIntegerField(max_length=10)),
            ],
        ),
        migrations.CreateModel(
            name='Resource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('file', models.FileField(upload_to='')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('downloads', models.PositiveSmallIntegerField(default=0)),
                ('category', models.ForeignKey(to='loads.Category', on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='Staff',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=100)),
                ('staff_number', models.CharField(max_length=20)),
                ('fte', models.PositiveSmallIntegerField(default=100)),
                ('user', models.OneToOneField(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'staff',
            },
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('url', models.URLField(null=True)),
                ('details', models.TextField()),
                ('deadline', models.DateTimeField()),
                ('archive', models.BooleanField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('category', models.ForeignKey(to='loads.Category', on_delete=models.CASCADE)),
                ('targets', models.ManyToManyField(to='loads.Staff')),
            ],
        ),
        migrations.CreateModel(
            name='TaskCompletion',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, primary_key=True, serialize=False)),
                ('comment', models.CharField(max_length=200, default='')),
                ('when', models.DateTimeField(auto_now_add=True)),
                ('staff', models.ForeignKey(to='loads.Staff', on_delete=models.CASCADE)),
                ('task', models.ForeignKey(to='loads.Task', on_delete=models.CASCADE)),
            ],
        ),
        migrations.AddField(
            model_name='activitytype',
            name='category',
            field=models.ForeignKey(to='loads.Category', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='activity',
            name='activity_type',
            field=models.ForeignKey(to='loads.ActivityType', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='activity',
            name='module',
            field=models.ForeignKey(null=True, to='loads.Module', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='activity',
            name='staff',
            field=models.ForeignKey(null=True, to='loads.Staff', on_delete=models.CASCADE),
        ),
    ]
