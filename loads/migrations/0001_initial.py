# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('name', models.CharField(max_length=100)),
                ('hours', models.PositiveSmallIntegerField()),
                ('percentage', models.PositiveSmallIntegerField()),
                ('hours_percentage', models.CharField(choices=[('H', 'Hours'), ('P', 'Percentage')], default='H', max_length=1)),
                ('semester', models.PositiveSmallIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='ActivityType',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('name', models.CharField(max_length=100)),
                ('category', models.CharField(choices=[('TEA', 'Teaching'), ('RES', 'Research'), ('ENT', 'Enterprise'), ('ADM', 'Admin'), ('OUT', 'Outreach')], default='TEA', max_length=2)),
            ],
        ),
        migrations.CreateModel(
            name='Module',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('module_code', models.CharField(max_length=10)),
                ('module_name', models.CharField(max_length=200)),
                ('semester', models.PositiveSmallIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='Staff',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('title', models.CharField(max_length=100)),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254)),
                ('staff_number', models.CharField(max_length=20)),
            ],
        ),
        migrations.AddField(
            model_name='activity',
            name='activity_type',
            field=models.ForeignKey(to='loads.ActivityType'),
        ),
        migrations.AddField(
            model_name='activity',
            name='module_id',
            field=models.ForeignKey(to='loads.Module'),
        ),
    ]
