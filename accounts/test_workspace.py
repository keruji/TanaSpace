from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class WorkspaceAccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="account", first_name="Existing", last_name="Name")
        self.client.force_login(self.user)

    def test_display_name_fallbacks(self):
        for nickname, first, last, expected in [
            (" Shelf Keeper ", "First", "Last", "Shelf Keeper"),
            (" ", " First ", " Last ", "First Last"),
            ("", "First", "", "First"), ("", "", "Last", "Last"),
            ("", "", "", "account"),
        ]:
            with self.subTest(expected=expected):
                self.user.nickname, self.user.first_name, self.user.last_name = nickname, first, last
                self.assertEqual(self.user.display_name, expected)

    def test_profile_only_saves_explicit_personal_fields(self):
        other = User.objects.create_user(username="other")
        response = self.client.post(reverse("accounts:profile"), {
            "nickname": "  Keeper  ", "first_name": "First", "last_name": "Last",
            "username": "stolen", "is_staff": "true", "id": other.pk, "email": "bad@example.com",
        }, headers={"HX-Request": "true", "HX-Target": "workspace-view"})
        self.assertEqual(response.headers["X-Workspace-Changed"], "profile")
        self.assertContains(response, "Your profile has been saved.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, "Keeper")
        self.assertEqual(self.user.username, "account")
        self.assertFalse(self.user.is_staff)
        self.assertEqual(self.user.email, "")
        other.refresh_from_db()
        self.assertEqual(other.nickname, "")
        self.assertContains(self.client.get(reverse("dashboard:index")), "Keeper")

    def test_invalid_profile_preserves_input_and_database(self):
        response = self.client.post(reverse("accounts:profile"), {
            "nickname": "x" * 81, "first_name": "Unsaved", "last_name": "Name",
        }, headers={"HX-Request": "true", "HX-Target": "workspace-view"})
        self.assertContains(response, 'value="Unsaved"')
        self.assertIn("nickname", response.context["form"].errors)
        self.assertNotIn("X-Workspace-Changed", response.headers)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Existing")

    def test_profile_csrf_and_regular_submission(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse("accounts:profile"), {"nickname": "No"}).status_code, 403)
        self.assertRedirects(self.client.post(reverse("accounts:profile"), {
            "nickname": "Yes", "first_name": "", "last_name": "",
        }), reverse("accounts:profile"))

    def test_full_and_partial_pages_and_expired_session(self):
        for name in ["dashboard:index", "items:index", "items:favorites", "accounts:profile", "accounts:settings", "item_types:index"]:
            url = reverse(name)
            with self.subTest(name=name):
                self.assertContains(self.client.get(url), '<header class="app-header">')
                partial = self.client.get(url, headers={"HX-Request": "true", "HX-Target": "workspace-view"})
                self.assertNotContains(partial, '<header class="app-header">')
                self.assertContains(partial, 'id="main"')
                self.assertIn("no-store", partial.headers["Cache-Control"])
                self.assertIn("HX-Target", partial.headers["Vary"])
                history = self.client.get(url, headers={"HX-History-Restore-Request": "true"})
                self.assertContains(history, '<header class="app-header">')
        self.client.logout()
        for headers in [{"HX-Request": "true"}, {"HX-History-Restore-Request": "true"}]:
            response = self.client.get(reverse("accounts:profile"), headers=headers)
            self.assertEqual(response.status_code, 204)
            self.assertTrue(response.headers["HX-Redirect"].startswith("/?next="))

    def test_settings_and_menu_keep_type_links_and_post_logout(self):
        page = self.client.get(reverse("accounts:settings"))
        self.assertContains(page, reverse("item_types:index"))
        self.assertNotContains(page, 'data-nav="item_types"')
        self.assertContains(page, 'data-logout')
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
