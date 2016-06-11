# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0006_require_contenttypes_0002'),
        ('loads', '0015_auto_20151210_1225'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkPackage',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('details', models.TextField()),
                ('startdate', models.DateField()),
                ('enddate', models.DateField()),
                ('draft', models.BooleanField(default=True)),
                ('archive', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('groups', models.ManyToManyField(blank=True, to='auth.Group')),
            ],
            options={
                'ordering': ['name', '-startdate'],
            },
        ),
    ]
