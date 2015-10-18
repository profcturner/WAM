# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0008_auto_20151017_1958'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='archive',
            field=models.BooleanField(default=False),
        ),
    ]
