from datetime import timedelta
from hashlib import sha256
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from item_types.models import ItemTypes, ItemTypeProperty
from items.models import Item
from .development_demo import COOKIE_NAME
from .models import DevelopmentDemoAccess

User = get_user_model()


@override_settings(DEBUG=True, DEV_DEMO_ENABLED=True)
class DevelopmentDemoTests(TestCase):
    def start(self):
        self.client.post(reverse("accounts:demo"))
        return User.objects.get(pk=self.client.session["_auth_user_id"])

    def workspace(self, user):
        kind = ItemTypes.objects.create(owner=user, name="Saved type", property_schema_version=1)
        prop = ItemTypeProperty.objects.create(item_type=kind, name="Brand", data_type="text")
        return Item.objects.create(owner=user, item_type=kind, name="Saved item", property_values={str(prop.pk): "Keep"})

    def test_logout_ends_session_and_demo_button_resumes_saved_account(self):
        user = self.start(); item = self.workspace(user)
        cookie = self.client.cookies[COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertEqual(cookie["path"], "/accounts/demo/")
        self.assertFalse(user.has_usable_password())
        access = DevelopmentDemoAccess.objects.get(user=user)
        self.assertEqual(access.token_hash, sha256(cookie.value.encode()).hexdigest())
        self.assertNotEqual(access.token_hash, cookie.value)
        self.assertRedirects(self.client.post(reverse("accounts:logout")), "/")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(Item.objects.filter(pk=item.pk).exists())
        self.assertRedirects(self.client.get(reverse("items:index")), "/?next=/tana/items/")
        self.client.post(reverse("accounts:demo"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertEqual(User.objects.count(), 1)
        self.assertContains(self.client.get(reverse("items:detail", args=[item.pk])), "Keep")

    def test_reset_confirmation_csrf_scope_and_token_rotation(self):
        user = self.start(); item = self.workspace(user)
        user.nickname = "Keeper"; user.save()
        other = User.objects.create_user(username="regular")
        private = self.workspace(other)
        url = reverse("accounts:reset_demo")
        old_cookie = self.client.cookies[COOKIE_NAME].value
        self.assertContains(self.client.get(url), "Reset Demo?")
        self.assertTrue(Item.objects.filter(pk=item.pk).exists())
        self.assertContains(self.client.post(url, {}), "Confirm that")
        csrf_client = Client(enforce_csrf_checks=True); csrf_client.force_login(user)
        self.assertEqual(csrf_client.post(url, {"confirm_reset": "yes"}).status_code, 403)
        self.assertRedirects(self.client.post(url, {"confirm_reset": "yes", "user_id": other.pk}), "/tana")
        user.refresh_from_db(); self.assertEqual(user.nickname, "Keeper")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertFalse(Item.objects.filter(owner=user).exists())
        self.assertFalse(ItemTypes.objects.filter(owner=user).exists())
        self.assertEqual(ItemTypeProperty.objects.filter(item_type__owner=user).count(), 0)
        self.assertTrue(Item.objects.filter(pk=private.pk).exists())
        self.assertNotEqual(self.client.cookies[COOKIE_NAME].value, old_cookie)
        self.client.post(reverse("accounts:logout")); self.client.post(reverse("accounts:demo"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_cleanup_and_capacity_exclude_development_demos(self):
        user = self.start(); self.workspace(user)
        User.objects.filter(pk=user.pk).update(date_joined=timezone.now() - timedelta(days=100))
        public = User.objects.create_user(username="old-public", is_demo=True)
        self.workspace(public)
        User.objects.filter(pk=public.pk).update(date_joined=timezone.now() - timedelta(days=100))
        call_command("cleanup_demo_users")
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(User.objects.filter(pk=public.pk).exists())
        with override_settings(DEV_DEMO_ENABLED=False, DEMO_MAX_ACTIVE_USERS=1):
            public_client = Client()
            self.assertEqual(public_client.post(reverse("accounts:demo")).status_code, 302)
            self.assertEqual(Client().post(reverse("accounts:demo")).status_code, 429)

    def test_missing_tampered_expired_and_separate_browser_tokens_do_not_resume(self):
        first = self.start()
        second_client = Client()
        second_client.post(reverse("accounts:demo"))
        self.assertNotEqual(int(second_client.session["_auth_user_id"]), first.pk)
        self.client.post(reverse("accounts:logout"))
        self.client.cookies[COOKIE_NAME] = "bad-token"
        second = self.start()
        self.assertNotEqual(first.pk, second.pk)
        self.client.post(reverse("accounts:logout"))
        DevelopmentDemoAccess.objects.filter(user=second).update(expires_at=timezone.now() - timedelta(seconds=1))
        third = self.start()
        self.assertNotEqual(second.pk, third.pk)
        self.assertTrue(User.objects.filter(pk=first.pk).exists())

    def test_feature_gate_regular_and_public_accounts(self):
        user = self.start()
        url = reverse("accounts:reset_demo")
        with override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False):
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, {"confirm_reset": "yes"}).status_code, 404)
            self.assertNotContains(self.client.get(reverse("accounts:settings")), "Reset Demo")
        with override_settings(DEV_DEMO_ENABLED=False):
            self.assertEqual(self.client.post(url, {"confirm_reset": "yes"}).status_code, 404)
        regular = User.objects.create_user(username="regular")
        self.client.force_login(regular)
        self.assertEqual(self.client.get(url).status_code, 404)
        regular.is_demo = True; regular.save()
        self.assertEqual(self.client.post(url, {"confirm_reset": "yes"}).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_production_demo_does_not_honor_resume_cookie(self):
        user = self.start(); self.client.post(reverse("accounts:logout"))
        with override_settings(DEBUG=False, DEV_DEMO_ENABLED=False, SECURE_SSL_REDIRECT=False):
            self.client.post(reverse("accounts:demo"))
        new = User.objects.get(pk=self.client.session["_auth_user_id"])
        self.assertNotEqual(user.pk, new.pk)
        self.assertFalse(new.is_development_demo)
