from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HelpTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user(username="help-user"))

    def test_menu_and_windows(self):
        dashboard = self.client.get(reverse("dashboard:index"))
        self.assertContains(dashboard, "Report a Bug")
        self.assertContains(dashboard, "https://github.com/keruji/TanaSpace/issues")
        about = self.client.get(reverse("help_about"), HTTP_HX_REQUEST="true", HTTP_HX_TARGET="modal-host")
        self.assertContains(about, "Version 0.1.0")
        self.assertContains(about, 'role="dialog"')
        licenses = self.client.get(reverse("help_licenses"), HTTP_HX_REQUEST="true", HTTP_HX_TARGET="modal-host")
        self.assertEqual(
            {entry["name"] for entry in licenses.context["licenses"]},
            {"TanaSpace", "OpenMoji", "Lucide", "Django", "htmx.org", "psycopg", "psycopg-binary", "gunicorn", "Markdown"},
        )
        self.assertIn("vite", {entry["name"] for entry in licenses.context["additional_licenses"]})
        self.assertContains(licenses, '<details class="additional-licenses">')
        for name in ("TanaSpace", "OpenMoji", "Lucide", "Django", "htmx.org"):
            self.assertContains(licenses, name)
        self.assertContains(licenses, "Attribution-ShareAlike 4.0 International")
        self.assertContains(licenses, '<h1 id="polyform-noncommercial-license-100">PolyForm Noncommercial License 1.0.0</h1>', html=True)
        self.assertContains(licenses, '<h1 id="vite-core-license">Vite core license</h1>', html=True)
        self.assertNotContains(licenses, '# PolyForm Noncommercial License')
        self.assertContains(licenses, "Markdown")
        self.assertEqual(self.client.get(reverse("help_licenses")).status_code, 200)
