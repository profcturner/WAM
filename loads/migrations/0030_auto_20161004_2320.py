# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('loads', '0029_auto_20160726_1915'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssessmentResource',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('details', models.TextField(blank=True)),
                ('resource', models.FileField(upload_to='assessments/%Y/%m/%d/')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('downloads', models.PositiveSmallIntegerField(default=0)),
                ('module', models.ForeignKey(to='loads.Module')),
            ],
        ),
        migrations.CreateModel(
            name='AssessmentResourceType',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='ExternalExaminer',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=100)),
                ('staff_number', models.CharField(max_length=20)),
                ('package', models.ForeignKey(to='loads.WorkPackage', null=True, on_delete=django.db.models.deletion.SET_NULL)),
                ('user', models.OneToOneField(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Programme',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('programme_code', models.CharField(max_length=10)),
                ('programme_name', models.CharField(max_length=200)),
                ('examiners', models.ManyToManyField(to='loads.ExternalExaminer', blank=True)),
            ],
            options={
                'ordering': ['programme_name'],
            },
        ),
        migrations.AddField(
            model_name='assessmentresource',
            name='resource_type',
            field=models.ForeignKey(to='loads.AssessmentResourceType'),
        ),
        migrations.AddField(
            model_name='module',
            name='lead_programme',
            field=models.ForeignKey(null=True, blank=True, to='loads.Programme'),
        ),
    ]
