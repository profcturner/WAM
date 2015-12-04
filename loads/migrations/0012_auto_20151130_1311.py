# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0011_auto_20151031_0106'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModuleSize',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('text', models.CharField(max_length=10)),
                ('admin_scaling', models.DecimalField(max_digits=6, decimal_places=2)),
                ('assessment_scaling', models.DecimalField(max_digits=6, decimal_places=2)),
            ],
        ),
        migrations.CreateModel(
            name='ModuleStaff',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('contact_proportion', models.PositiveSmallIntegerField()),
                ('admin_proportion', models.PositiveSmallIntegerField()),
                ('assessment_proportion', models.PositiveSmallIntegerField()),
            ],
            options={
                'verbose_name_plural': 'modulestaff',
            },
        ),
        migrations.AddField(
            model_name='module',
            name='admin_hours',
            field=models.PositiveSmallIntegerField(blank=True, default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='module',
            name='assessment_hours',
            field=models.PositiveSmallIntegerField(blank=True, default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='module',
            name='contact_hours',
            field=models.PositiveSmallIntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='module',
            name='credits',
            field=models.PositiveSmallIntegerField(default=20),
        ),
        migrations.AddField(
            model_name='modulestaff',
            name='module',
            field=models.ForeignKey(to='loads.Module'),
        ),
        migrations.AddField(
            model_name='modulestaff',
            name='staff',
            field=models.ForeignKey(to='loads.Staff'),
        ),
        migrations.AddField(
            model_name='module',
            name='size',
            field=models.ForeignKey(to='loads.ModuleSize', default=1),
            preserve_default=False,
        ),
    ]
