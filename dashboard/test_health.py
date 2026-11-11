from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    def test_health_is_available_without_login(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_health_reports_database_failure_without_details(self):
        with patch(
            "config.views.connection.cursor",
            side_effect=OperationalError("private database error details"),
        ):
            response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotContains(
            response,
            "private database error details",
            status_code=503,
        )

    def test_health_rejects_post_requests(self):
        response = self.client.post(reverse("health"))

        self.assertEqual(response.status_code, 405)