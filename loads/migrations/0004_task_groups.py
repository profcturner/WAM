# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0006_require_contenttypes_0002'),
        ('loads', '0003_auto_20151017_1325'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='groups',
            field=models.ManyToManyField(to='auth.Group'),
        ),
    ]
