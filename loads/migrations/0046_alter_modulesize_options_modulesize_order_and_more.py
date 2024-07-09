# Generated by Django 4.2.13 on 2024-07-09 17:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0045_auto_20211129_2143'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='modulesize',
            options={'ordering': ['order']},
        ),
        migrations.AddField(
            model_name='modulesize',
            name='order',
            field=models.IntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='workpackage',
            name='credit_contact_scaling',
            field=models.FloatField(default=2.5),
        ),
    ]
