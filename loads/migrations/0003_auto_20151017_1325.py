# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0002_auto_20151017_1150'),
    ]

    operations = [
        migrations.AlterOrderWithRespectTo(
            name='staff',
            order_with_respect_to='user',
        ),
    ]
