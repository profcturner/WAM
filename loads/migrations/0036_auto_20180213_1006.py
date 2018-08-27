# Generated by Django 2.0 on 2018-02-13 10:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loads', '0035_auto_20171018_1421'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='assessmentstaff',
            options={'verbose_name_plural': 'assessment staff'},
        ),
        migrations.AlterField(
            model_name='activity',
            name='staff',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='loads.Staff'),
        ),
        migrations.AlterField(
            model_name='module',
            name='coordinator',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='coordinated_modules', to='loads.Staff'),
        ),
        migrations.AlterField(
            model_name='module',
            name='lead_programme',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lead_modules', to='loads.Programme'),
        ),
    ]