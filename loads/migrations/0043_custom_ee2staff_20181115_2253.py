# Generated by Django 2.1.1 on 2018-11-15 22:53

from django.db import migrations, models


def migrate_externals(apps, schema_editor):
    """This migration is part of moving ExternalExaminer objects to Staff
    where we will copy them first, before eventually dropping the former"""

    # We can't import the models directly as it may be a newer
    # version than this migration expects. We use the historical versions.
    ExternalExaminer = apps.get_model('loads', 'ExternalExaminer')
    Staff = apps.get_model('loads', 'Staff')
    Programme = apps.get_model('loads', 'Programme')

    # We need to create a Staff object for each Examiner, and keep the mapping
    examiner_staff_mapping = dict()

    for examiner in ExternalExaminer.objects.all():
        # Create a "matching" Staff user
        staff = Staff.objects.create(
            user=examiner.user,
            title=examiner.title,
            staff_number=examiner.staff_number,
            fte=1,
            is_external=True,
            has_workload=False,
            package=examiner.package
        )

        # Keep a record of the mapping
        examiner_staff_mapping.update({examiner: staff})

    # Now map Programmes, at this stage the ExternalExaminer objects should be in
    # deprecated_examiners, and we have an empty column of examiners of Staff objects
    for programme in Programme.objects.all():
        # Map each examiner
        for examiner in programme.deprecated_examiners.all():
            programme.examiners.add(examiner_staff_mapping[examiner])
        # And save the selection.
        programme.save()


class Migration(migrations.Migration):



    dependencies = [
        ('loads', '0042_custom_ee2staff_20181115_2251'),
    ]

    operations = [
        migrations.RenameField(
            model_name='Programme',
            old_name='examiners',
            new_name='deprecated_examiners'
        ),
        migrations.AddField(
            model_name='Programme',
            name='examiners',
            field=models.ManyToManyField(to='loads.Staff', blank=True, null=True,
                                         limit_choices_to={'is_external': True})
        ),
        migrations.RunPython(migrate_externals),
        migrations.RemoveField(
            model_name='Programme',
            name='deprecated_examiners',
        ),
        migrations.AlterField(
            model_name='activity',
            name='staff',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_external': False}, null=True,
                                    on_delete=models.deletion.SET_NULL, to='loads.Staff'),
        ),
        migrations.AlterField(
            model_name='assessmentstaff',
            name='staff',
            field=models.ForeignKey(limit_choices_to={'is_external': False},
                                    on_delete=models.deletion.CASCADE, to='loads.Staff'),
        ),
        migrations.AlterField(
            model_name='module',
            name='coordinator',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_external': False}, null=True,
                                    on_delete=models.deletion.SET_NULL, related_name='coordinated_modules',
                                    to='loads.Staff'),
        ),
        migrations.AlterField(
            model_name='module',
            name='moderators',
            field=models.ManyToManyField(blank=True, limit_choices_to={'is_external': False},
                                         related_name='moderated_modules', to='loads.Staff'),
        ),
        migrations.AlterField(
            model_name='programme',
            name='directors',
            field=models.ManyToManyField(blank=True, limit_choices_to={'is_external': False},
                                         related_name='directed_programmes', to='loads.Staff'),
        ),
        migrations.AlterField(
            model_name='programme',
            name='examiners',
            field=models.ManyToManyField(blank=True, limit_choices_to={'is_external': True},
                                         related_name='examined_programmes', to='loads.Staff'),
        ),
        migrations.AlterField(
            model_name='projectstaff',
            name='staff',
            field=models.ForeignKey(limit_choices_to={'is_external': False},
                                    on_delete=models.deletion.CASCADE, to='loads.Staff'),
        ),
    ]
