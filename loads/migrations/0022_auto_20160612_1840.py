# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0021_auto_20160612_1602'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='activity',
            name='academic_year',
        ),
        migrations.RemoveField(
            model_name='modulestaff',
            name='academic_year',
        ),
    ]
