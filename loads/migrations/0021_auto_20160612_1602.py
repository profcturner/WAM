# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0020_auto_20160612_1600'),
    ]

    operations = [
        migrations.AlterField(
            model_name='modulesize',
            name='admin_scaling',
            field=models.FloatField(),
        ),
        migrations.AlterField(
            model_name='modulesize',
            name='assessment_scaling',
            field=models.FloatField(),
        ),
    ]
