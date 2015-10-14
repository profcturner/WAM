# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StaffActivity',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('activity_id', models.ForeignKey(to='loads.Activity')),
            ],
        ),
        migrations.AddField(
            model_name='staff',
            name='fte',
            field=models.PositiveSmallIntegerField(default=100),
        ),
        migrations.AlterField(
            model_name='activitytype',
            name='category',
            field=models.CharField(max_length=3, default='TEA', choices=[('TEA', 'Teaching'), ('RES', 'Research'), ('ENT', 'Enterprise'), ('ADM', 'Admin'), ('OUT', 'Outreach')]),
        ),
        migrations.AddField(
            model_name='staffactivity',
            name='staff_id',
            field=models.ForeignKey(to='loads.Staff'),
        ),
    ]
