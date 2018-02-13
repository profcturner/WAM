# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0016_workpackage'),
    ]

    operations = [
        migrations.AddField(
            model_name='activity',
            name='package',
            field=models.ForeignKey(to='loads.WorkPackage', default=1, on_delete=models.CASCADE),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='module',
            name='package',
            field=models.ForeignKey(to='loads.WorkPackage', default=1, on_delete=models.CASCADE),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='staff',
            name='package',
            field=models.ForeignKey(to='loads.WorkPackage', default=1, on_delete=models.SET_NULL),
            preserve_default=False,
        ),
    ]
