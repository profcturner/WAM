# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0031_auto_20161007_2209'),
    ]

    operations = [
        migrations.AddField(
            model_name='assessmentresource',
            name='owner',
            field=models.ForeignKey(to='loads.Staff', default=1),
            preserve_default=False,
        ),
    ]
