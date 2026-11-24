from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from item_types.models import ItemTypes
from .models import Item

User = get_user_model()
PARTIAL = {"HX-Request": "true", "HX-Target": "modal-host"}


class WorkspaceItemTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner")
        self.other = User.objects.create_user(username="other")
        self.kind = ItemTypes.objects.create(owner=self.user, name="Tools")
        self.other_kind = ItemTypes.objects.create(owner=self.other, name="Private")
        self.item = Item.objects.create(owner=self.user, item_type=self.kind, name="Garden Hammer")
        self.private = Item.objects.create(owner=self.other, item_type=self.other_kind, name="Private Hammer")
        self.client.force_login(self.user)

    def test_search_filters_and_favorites_are_owner_scoped(self):
        second = ItemTypes.objects.create(owner=self.user, name="Kitchen")
        Item.objects.create(owner=self.user, item_type=second, name="Kitchen Hammer")
        url = reverse("items:index")
        response = self.client.get(url, {"q": "  HAMMER  ", "type": self.kind.pk})
        self.assertEqual([item.pk for item in response.context["items"]], [self.item.pk])
        invalid = self.client.get(url, {"type": self.other_kind.pk})
        self.assertEqual(len(invalid.context["items"]), 0)
        self.assertNotContains(invalid, "Private Hammer")
        self.assertIn("type", invalid.context["search_form"].errors)
        self.assertIn("q", self.client.get(url, {"q": "x" * 161}).context["search_form"].errors)
        self.assertEqual(len(self.client.get(reverse("items:favorites")).context["items"]), 0)

    def test_favorite_is_post_only_private_idempotent_and_csrf_protected(self):
        url = reverse("items:favorite", args=[self.item.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, {"favorite": "bad"}).status_code, 400)
        checked = Client(enforce_csrf_checks=True)
        checked.force_login(self.user)
        self.assertEqual(checked.post(url, {"favorite": "true"}).status_code, 403)
        for _ in range(2):
            self.assertEqual(self.client.post(url, {"favorite": "true"}, headers=PARTIAL).status_code, 200)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_favorite)
        self.assertIsNone(self.item.edited_at)
        self.assertEqual(len(self.client.get(reverse("items:favorites")).context["items"]), 1)
        self.assertEqual(self.client.post(reverse("items:favorite", args=[self.private.pk]), {"favorite": "true"}).status_code, 404)

    def test_partial_create_edit_delete_and_bound_validation(self):
        url = reverse("items:create")
        window = self.client.get(url, headers=PARTIAL)
        self.assertContains(window, 'role="dialog"')
        self.assertNotContains(window, 'id="main"')
        invalid = self.client.post(url, {"name": "", "item_type": self.kind.pk, "notes": "Keep this"}, headers=PARTIAL)
        self.assertIn("name", invalid.context["form"].errors)
        self.assertContains(invalid, "Keep this")
        created = self.client.post(url, {"name": "New tool", "item_type": self.kind.pk}, headers=PARTIAL)
        item = Item.objects.get(name="New tool")
        self.assertEqual(created.headers["X-Workspace-URL"], reverse("items:detail", args=[item.pk]))
        self.assertNotContains(created, '<header')
        edited = self.client.post(reverse("items:edit", args=[item.pk]), {"name": "Updated", "item_type": self.kind.pk}, headers=PARTIAL)
        self.assertContains(edited, "Updated")
        removed = self.client.post(reverse("items:delete", args=[item.pk]), headers=PARTIAL)
        self.assertEqual(removed.headers["X-Workspace-Close"], "true")
        self.assertFalse(Item.objects.filter(pk=item.pk).exists())

    def test_partial_type_mutations_counts_and_protected_delete(self):
        created = self.client.post(reverse("item_types:create"), {"name": "New type"}, headers=PARTIAL)
        kind = ItemTypes.objects.get(name="New type")
        self.assertEqual(created.headers["X-Workspace-Changed"], "types")
        self.assertContains(self.client.get(reverse("item_types:index")), "1 item")
        protected = self.client.post(reverse("item_types:delete", args=[self.kind.pk]), headers=PARTIAL)
        self.assertContains(protected, "Move or delete those items first")
        self.assertNotIn("X-Workspace-Close", protected.headers)
        self.assertTrue(ItemTypes.objects.filter(pk=self.kind.pk).exists())
        self.assertEqual(self.client.post(reverse("item_types:delete", args=[kind.pk]), headers=PARTIAL).headers["X-Workspace-Close"], "true")

    def test_return_urls_cannot_escape_workspace_and_preserve_filters(self):
        url = reverse("items:detail", args=[self.item.pk])
        for bad in ["https://example.com/", "//example.com", "/admin/", "https://[", "/accounts/logout/"]:
            response = self.client.get(url, {"return_to": bad}, headers=PARTIAL)
            self.assertEqual(response.context["return_to"], reverse("items:index"))
        good = reverse("items:index") + "?q=Hammer&type=" + str(self.kind.pk)
        self.assertEqual(self.client.get(url, {"return_to": good}, headers=PARTIAL).context["return_to"], good)

    def test_pagination_filter_state_and_bounded_queries(self):
        Item.objects.bulk_create([Item(owner=self.user, item_type=self.kind, name=f"Hammer {i}") for i in range(44)])
        with self.assertNumQueries(7):  # Includes both filter choice lists; no N+1.
            response = self.client.get(reverse("items:index"), {"q": "Hammer", "page": 2}, headers={"HX-Request": "true", "HX-Target": "main"})
        self.assertEqual(len(response.context["items"]), 5)
        self.assertContains(response, "q=Hammer")
        self.assertEqual(response.context["item_count"], 45)

    def test_expanded_schema_accepts_previous_release_inserts(self):
        apps = MigrationExecutor(connection).loader.project_state([
            ("accounts", "0002_user_is_demo"), ("items", "0006_alter_item_description_alter_item_notes"),
        ]).apps
        old_user = apps.get_model("accounts", "User").objects.create(username="old-release")
        old_type = apps.get_model("item_types", "ItemTypes").objects.create(owner_id=old_user.pk, name="Old type")
        old_item = apps.get_model("items", "Item").objects.create(owner_id=old_user.pk, item_type_id=old_type.pk, name="Old item")
        self.assertEqual(User.objects.get(pk=old_user.pk).nickname, "")
        self.assertFalse(Item.objects.get(pk=old_item.pk).is_favorite)


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locking")
class ConcurrentQuotaTests(TransactionTestCase):
    def test_two_creates_cannot_exceed_item_quota(self):
        user = User.objects.create_user(username="quota")
        kind = ItemTypes.objects.create(owner=user, name="Tools")
        Item.objects.bulk_create([Item(owner=user, item_type=kind, name=f"Tool {i}") for i in range(99)])
        def create(number):
            close_old_connections()
            try:
                client = Client()
                client.force_login(User.objects.get(pk=user.pk))
                return client.post(reverse("items:create"), {"name": f"Concurrent {number}", "item_type": kind.pk}).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(create, [1, 2]))
        self.assertEqual(sorted(statuses), [200, 302])
        self.assertEqual(Item.objects.filter(owner=user).count(), 100)
