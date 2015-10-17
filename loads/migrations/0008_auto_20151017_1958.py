# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0007_auto_20151017_1422'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='groups',
            field=models.ManyToManyField(blank=True, null=True, to='auth.Group'),
        ),
        migrations.AlterField(
            model_name='task',
            name='targets',
            field=models.ManyToManyField(blank=True, null=True, to='loads.Staff'),
        ),
    ]
