# Standard Imports
from io import StringIO
import logging

from django.core.exceptions import PermissionDenied
# Django specific Imports
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

# Import Some Django models that we use

from django.contrib.auth.models import User, Group


# Import some models

from .models import ActivityGenerator
from .models import ActivitySet
from .models import ActivityType
from .models import Activity
from .models import AssessmentResource
from .models import AssessmentResourceType
from .models import AssessmentStaff
from .models import Category
from .models import Campus
from .models import ExternalExaminer
from .models import Staff
from .models import Task
from .models import Activity
from .models import TaskCompletion
from .models import Module
from .models import ModuleSize
from .models import ModuleStaff
from .models import Programme
from .models import Project
from .models import ProjectStaff
from .models import WorkPackage


class CommandsTestCase(TestCase):

    def setUp(self):
        # Logging is very noisy typically
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        # Put the logging back in place
        logging.disable(logging.NOTSET)

    """Test Populate Database commands, which can fail due to schema changes"""
    def test_create_schema(self):
        """ Test creation of scheme through --add-core-config """

        out = StringIO()
        args = ['--add-core-config']
        opts = {}
        call_command('populate_database', stdout=out, *args, **opts)
        self.assertIn("Complete.", out.getvalue())


    def test_create_test_data_no_config(self):
        """ Test that --add-test-data misfires correctly if we haven't called --add-core-config """

        out = StringIO()
        err = StringIO()
        args = ['--add-test-data']
        opts = {}

        call_command('populate_database', stdout=out, stderr=err, *args, **opts)
        self.assertIn("no basic schema", err.getvalue())


    def test_create_test_data(self):
        " Test my custom command."

        out = StringIO()
        args = ['--add-core-config']
        opts = {}
        call_command('populate_database', stdout=out, *args, **opts)

        args = ['--add-test-data']
        opts = {}
        call_command('populate_database', stdout=out, *args, **opts)
        self.assertIn("Complete.", out.getvalue())

