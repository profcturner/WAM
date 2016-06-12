# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0019_auto_20160612_1442'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workpackage',
            name='contact_admin_scaling',
            field=models.FloatField(default=1),
        ),
        migrations.AlterField(
            model_name='workpackage',
            name='contact_assessment_scaling',
            field=models.FloatField(default=1),
        ),
        migrations.AlterField(
            model_name='workpackage',
            name='credit_contact_scaling',
            field=models.FloatField(default=0.4),
        ),
    ]
