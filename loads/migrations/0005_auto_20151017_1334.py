# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0004_task_groups'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activity',
            name='module',
            field=models.ForeignKey(null=True, blank=True, to='loads.Module'),
        ),
    ]
