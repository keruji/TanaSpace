from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from datetime import timedelta
from django.test import Client, TestCase
from django.urls import reverse

from items.models import Item
from item_types.models import ItemTypes

User = get_user_model()


class DemoFlowTests(TestCase):
    def test_landing_offers_demo_without_login_or_signup(self):
        response = self.client.get(reverse("landing"))
        self.assertContains(response, 'action="/accounts/demo/"', count=2)
        self.assertNotContains(response, reverse("accounts:login"))
        self.assertNotContains(response, reverse("accounts:signup"))

    def test_demo_creates_session_scoped_user(self):
        self.assertEqual(self.client.get(reverse("accounts:demo")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("accounts:demo")), "/tana")
        user = User.objects.get()
        self.assertTrue(user.is_demo)
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)
        self.assertRegex(user.username, r"^demo\d{9}$")
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertLessEqual(self.client.session.get_expiry_age(), settings.DEMO_ACCOUNT_TTL_SECONDS)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertContains(self.client.get("/tana"), user.username)
        self.assertRedirects(self.client.post(reverse("accounts:demo")), "/tana")
        self.assertEqual(User.objects.count(), 1)

    def test_expired_demo_account_and_data_are_cleaned(self):
        self.client.post(reverse("accounts:demo"))
        user = User.objects.get()
        item_type = ItemTypes.objects.create(owner=user, name="Temporary type")
        Item.objects.create(owner=user, item_type=item_type, name="Temporary item")
        User.objects.filter(pk=user.pk).update(
            date_joined=timezone.now() - timedelta(seconds=settings.DEMO_ACCOUNT_TTL_SECONDS + 1)
        )
        call_command("cleanup_demo_users")
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(Item.objects.filter(name="Temporary item").exists())
        self.assertFalse(ItemTypes.objects.filter(name="Temporary type").exists())

    @override_settings(DEMO_MAX_ACTIVE_USERS=1)
    def test_demo_capacity_is_bounded(self):
        self.assertRedirects(self.client.post(reverse("accounts:demo")), "/tana")
        other_client = Client()
        response = other_client.post(reverse("accounts:demo"))
        self.assertEqual(response.status_code, 429)
        self.assertEqual(User.objects.filter(is_demo=True).count(), 1)

    def test_separate_sessions_have_private_demo_data(self):
        other_client = Client()
        self.client.post(reverse("accounts:demo"))
        first_user = User.objects.get()
        Item.objects.create(owner=first_user, item_type=ItemTypes.objects.create(owner=first_user, name="Demo type"), name="Only in first demo")
        other_client.post(reverse("accounts:demo"))
        second_user = User.objects.exclude(pk=first_user.pk).get()
        self.assertNotEqual(first_user.pk, second_user.pk)
        self.assertNotContains(other_client.get(reverse("items:index")), "Only in first demo")
        self.assertContains(self.client.get(reverse("items:index")), "Only in first demo")

    def test_logout_returns_home_and_deletes_demo_data(self):
        self.client.post(reverse("accounts:demo"))
        user = User.objects.get()
        Item.objects.create(owner=user, item_type=ItemTypes.objects.create(owner=user, name="Demo type"), name="Temporary item")
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("accounts:logout")), "/")
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(Item.objects.filter(name="Temporary item").exists())
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.get("/tana"), "/?next=/tana")

    def test_regular_account_is_preserved_on_logout(self):
        user = User.objects.create_user(username="existing-user")
        self.client.force_login(user)
        self.assertRedirects(self.client.post(reverse("accounts:logout")), "/")
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_login_and_signup_are_disabled(self):
        for name in ("accounts:login", "accounts:signup"):
            with self.subTest(name=name):
                self.assertRedirects(self.client.get(reverse(name)), "/")
                self.assertRedirects(self.client.post(reverse(name), {
                    "username": "new-user", "password1": "Some-password-473!",
                    "password2": "Some-password-473!",
                }), "/")
        self.assertFalse(User.objects.exists())

    def test_demo_and_logout_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("accounts:demo")).status_code, 403)
        landing = client.get(reverse("landing"))
        token = landing.cookies["csrftoken"].value
        self.assertRedirects(client.post(reverse("accounts:demo"), {
            "csrfmiddlewaretoken": token,
        }), "/tana")
        self.assertEqual(client.post(reverse("accounts:logout")).status_code, 403)
        self.assertRedirects(client.post(reverse("accounts:logout"), {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        }), "/")
