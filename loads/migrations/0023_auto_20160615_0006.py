# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0022_auto_20160612_1840'),
    ]

    operations = [
        migrations.AlterField(
            model_name='staff',
            name='package',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='loads.WorkPackage'),
        ),
    ]
