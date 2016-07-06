# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0027_auto_20160701_1701'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='activitygenerator',
            options={'ordering': ['name']},
        ),
        migrations.AddField(
            model_name='module',
            name='details',
            field=models.TextField(null=True, blank=True),
        ),
    ]
