from django.contrib.auth import get_user_model
from django.test import TestCase


class DashboardTests(TestCase):
    def test_dashboard_requires_login_and_slash_redirect_preserves_protection(self):
        self.assertRedirects(self.client.get("/tana"), "/?next=/tana")
        self.assertRedirects(self.client.get("/tana/"), "/tana", fetch_redirect_response=False)

    def test_dashboard_displays_only_signed_in_account(self):
        user = get_user_model().objects.create_user(username="my-space")
        get_user_model().objects.create_user(username="other-private-account")
        self.client.force_login(user)
        response = self.client.get("/tana")
        self.assertContains(response, "my-space")
        self.assertNotContains(response, "other-private-account")
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "My Tana")
        self.assertContains(response, "Favorites")
        self.assertIn("no-store", response.headers["Cache-Control"])
