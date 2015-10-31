# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0009_auto_20151018_0817'),
    ]

    operations = [
        migrations.CreateModel(
            name='Campus',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, verbose_name='ID', primary_key=True)),
                ('name', models.CharField(max_length=100)),
            ],
        ),
        migrations.AlterField(
            model_name='task',
            name='groups',
            field=models.ManyToManyField(to='auth.Group', blank=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='targets',
            field=models.ManyToManyField(to='loads.Staff', blank=True),
        ),
    ]
