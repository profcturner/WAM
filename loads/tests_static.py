"""Tests for static file configuration"""
import os

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.checks import run_checks
from django.test import SimpleTestCase


class StaticFilesTestCase(SimpleTestCase):

    def test_patched_formset_js_wins(self):
        """loads ships a patched fancy_formset/formset.js that keeps deleted rows in TOTAL_FORMS,
        so Django receives and deletes them. It must take precedence over the package's copy."""
        found = finders.find('fancy_formset/formset.js')
        self.assertEqual(os.path.realpath(found),
                         os.path.realpath(os.path.join(settings.BASE_DIR, 'loads', 'static', 'fancy_formset',
                                                       'formset.js')))
        with open(found) as f:
            self.assertIn('deactivateForm(t){this.render()', f.read(),
                          "the patch (deactivating a form doesn't reduce numForms) is missing")

    def test_no_static_configuration_errors(self):
        errors = [e for e in run_checks() if e.id.startswith('staticfiles.') and e.is_serious()]
        self.assertEqual(errors, [])
