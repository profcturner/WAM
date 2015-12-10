# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0014_auto_20151207_1909'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='activitytype',
            options={'ordering': ['name']},
        ),
        migrations.AlterModelOptions(
            name='campus',
            options={'verbose_name_plural': 'campuses', 'ordering': ['name']},
        ),
        migrations.AlterModelOptions(
            name='module',
            options={'ordering': ['module_code']},
        ),
    ]
