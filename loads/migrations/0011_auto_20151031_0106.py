# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0010_auto_20151031_0058'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='campus',
            options={'verbose_name_plural': 'campuses'},
        ),
        migrations.AddField(
            model_name='module',
            name='campus',
            field=models.ForeignKey(default=1, to='loads.Campus', on_delete=models.CASCADE),
            preserve_default=False,
        ),
    ]
