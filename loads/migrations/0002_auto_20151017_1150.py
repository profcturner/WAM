# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='category',
            options={'verbose_name_plural': 'categories'},
        ),
        migrations.AlterField(
            model_name='activity',
            name='comment',
            field=models.CharField(max_length=200, default='', blank=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='url',
            field=models.URLField(default='', blank=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='taskcompletion',
            name='comment',
            field=models.CharField(max_length=200, default='', blank=True),
        ),
    ]
