# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0025_auto_20160627_1407'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='body',
            options={'verbose_name_plural': 'bodies', 'ordering': ['name']},
        ),
        migrations.AlterModelOptions(
            name='project',
            options={'ordering': ['name', '-start']},
        ),
        migrations.AlterModelOptions(
            name='projectstaff',
            options={'verbose_name_plural': 'project staff', 'ordering': ['staff', '-start']},
        ),
    ]
