"""Tests for data migrations"""
import datetime

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class TaskOwnerPackageBackfillTests(TransactionTestCase):
    """0058 fills in the owner and package of existing tasks where it can"""
    before = [('loads', '0057_alter_module_size'), ('admin', '0003_logentry_add_action_flag_choices'),
              ('contenttypes', '0002_remove_content_type_name')]
    after = [('loads', '0058_task_owner_package_visibility')]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        apps = executor.loader.project_state(self.before).apps

        User = apps.get_model('auth', 'User')
        Group = apps.get_model('auth', 'Group')
        Staff = apps.get_model('loads', 'Staff')
        WorkPackage = apps.get_model('loads', 'WorkPackage')
        Category = apps.get_model('loads', 'Category')
        Task = apps.get_model('loads', 'Task')
        LogEntry = apps.get_model('admin', 'LogEntry')
        ContentType = apps.get_model('contenttypes', 'ContentType')

        school = Group.objects.create(name="School")
        other = Group.objects.create(name="Other school")
        this_year = WorkPackage.objects.create(name="2017/18", details="", startdate=datetime.date(2017, 9, 1),
                                               enddate=datetime.date(2018, 8, 31))
        next_year = WorkPackage.objects.create(name="2018/19", details="", startdate=datetime.date(2018, 9, 1),
                                               enddate=datetime.date(2019, 8, 31))
        elsewhere = WorkPackage.objects.create(name="Elsewhere", details="", startdate=datetime.date(2017, 9, 1),
                                               enddate=datetime.date(2018, 8, 31))
        this_year.groups.add(school)
        next_year.groups.add(school)
        elsewhere.groups.add(other)

        admin_user = User.objects.create(username='admin')
        self.admin_staff = Staff.objects.create(user=admin_user, staff_number='admin')
        target_user = User.objects.create(username='lecturer')
        target_user.groups.add(school)
        target = Staff.objects.create(user=target_user, staff_number='lecturer')

        category = Category.objects.create(name="Admin", abbreviation="admin", colour="blue")
        in_term = timezone.make_aware(datetime.datetime(2018, 1, 15, 9, 0))

        def task(name, deadline=in_term):
            return Task.objects.create(name=name, details="", category=category, deadline=deadline)

        # Aimed at the School by group, with a deadline in 2017/18 (the School has two packages)
        self.by_group = task("By group")
        self.by_group.groups.add(school)
        # Aimed at a member of the School individually, deadline in 2018/19
        self.by_target = task("By target", timezone.make_aware(datetime.datetime(2019, 1, 15, 9, 0)))
        self.by_target.targets.add(target)
        # Aimed at a group in a single package, deadline outside it: the only candidate
        self.single = task("Single candidate", timezone.make_aware(datetime.datetime(2025, 1, 1, 9, 0)))
        self.single.groups.add(other)
        # Aimed at no one, so no package can be worked out
        self.nobody = task("Nobody")
        # Created through Django admin, by admin_user
        self.via_admin = task("Via admin")
        content_type, _ = ContentType.objects.get_or_create(app_label='loads', model='task')
        LogEntry.objects.create(user=admin_user, content_type=content_type, object_id=str(self.via_admin.pk),
                                object_repr="Via admin", action_flag=1, action_time=timezone.now())
        self.ids = {'this_year': this_year.pk, 'next_year': next_year.pk, 'elsewhere': elsewhere.pk}

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.after)
        self.apps = executor.loader.project_state(self.after).apps

    def tearDown(self):
        # Leave the database fully migrated for other tests
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_backfill(self):
        Task = self.apps.get_model('loads', 'Task')
        package = {t.name: t.package_id for t in Task.objects.all()}
        self.assertEqual(package["By group"], self.ids['this_year'])
        self.assertEqual(package["By target"], self.ids['next_year'])
        self.assertEqual(package["Single candidate"], self.ids['elsewhere'])
        self.assertIsNone(package["Nobody"])

        owner = {t.name: t.owner_id for t in Task.objects.all()}
        self.assertEqual(owner["Via admin"], self.admin_staff.pk)
        self.assertIsNone(owner["By group"])
        self.assertTrue(all(t.targets_see_completion for t in Task.objects.all()))
