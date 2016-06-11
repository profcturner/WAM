# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0017_auto_20160610_2238'),
    ]

    operations = [
        migrations.AddField(
            model_name='modulestaff',
            name='package',
            field=models.ForeignKey(default=1, to='loads.WorkPackage'),
            preserve_default=False,
        ),
    ]
