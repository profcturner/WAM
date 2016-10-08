# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0030_auto_20161004_2320'),
    ]

    operations = [
        migrations.AddField(
            model_name='module',
            name='moderators',
            field=models.ManyToManyField(blank=True, to='loads.Staff'),
        ),
        migrations.AddField(
            model_name='programme',
            name='directors',
            field=models.ManyToManyField(blank=True, to='loads.Staff'),
        ),
        migrations.AddField(
            model_name='programme',
            name='package',
            field=models.ForeignKey(default=1, to='loads.WorkPackage'),
            preserve_default=False,
        ),
    ]
