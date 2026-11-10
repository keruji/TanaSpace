from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from items.models import Item
from .models import ItemTypes


class ItemTypeFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="type-owner")
        cls.other = get_user_model().objects.create_user(username="type-other")
        cls.item_type = ItemTypes.objects.create(owner=cls.owner, name="Tools")
        cls.other_type = ItemTypes.objects.create(owner=cls.other, name="Private")

    def setUp(self):
        self.client.force_login(self.owner)

    def test_create_view_edit_and_delete_type(self):
        self.assertContains(self.client.get(reverse("item_types:create")), 'role="dialog"')
        response = self.client.post(reverse("item_types:create"), {
            "name": "Supplies", "sequence": 3, "active": "on", "description": "Useful things",
        })
        created = ItemTypes.objects.get(owner=self.owner, name="Supplies")
        self.assertRedirects(response, reverse("item_types:detail", args=[created.pk]))
        detail = self.client.get(reverse("item_types:detail", args=[created.pk]))
        self.assertContains(detail, "Useful things")
        self.assertNotContains(detail, '<textarea name="description"')
        self.assertNotContains(detail, "<dt>Sequence</dt>")
        self.assertNotContains(detail, "<dt>Status</dt>")
        self.assertEqual(created.sequence, 0)
        self.assertTrue(created.active)
        self.assertRedirects(self.client.post(reverse("item_types:edit", args=[created.pk]), {
            "name": "Equipment", "sequence": 2, "active": "on", "description": "Changed",
        }), reverse("item_types:detail", args=[created.pk]))
        self.assertEqual(ItemTypes.objects.get(pk=created.pk).name, "Equipment")
        self.assertRedirects(self.client.post(reverse("item_types:delete", args=[created.pk])), reverse("item_types:index"))
        self.assertFalse(ItemTypes.objects.filter(pk=created.pk).exists())

    def test_used_type_cannot_be_deleted(self):
        Item.objects.create(owner=self.owner, item_type=self.item_type, name="Hammer")
        page = self.client.get(reverse("item_types:delete", args=[self.item_type.pk]))
        self.assertContains(page, "Move or delete those items first")
        self.assertNotContains(page, "Delete type</button>")
        self.assertRedirects(self.client.post(reverse("item_types:delete", args=[self.item_type.pk])), reverse("item_types:detail", args=[self.item_type.pk]))
        self.assertTrue(ItemTypes.objects.filter(pk=self.item_type.pk).exists())
        with self.assertRaises(ProtectedError):
            self.item_type.delete()

    def test_other_users_type_is_private(self):
        self.assertNotContains(self.client.get(reverse("item_types:index")), "Private")
        for name in ("detail", "edit", "delete"):
            url = reverse(f"item_types:{name}", args=[self.other_type.pk])
            self.assertEqual(self.client.get(url).status_code, 404)
            if name != "detail":
                self.assertEqual(self.client.post(url, {"name": "Stolen"}).status_code, 404)

    def test_list_is_limited_to_40_in_sequence_order(self):
        for number in range(45):
            ItemTypes.objects.create(owner=self.owner, name=f"Type {number}", sequence=number + 1)
        page = self.client.get(reverse("item_types:index"))
        self.assertEqual(len(page.context["item_types"]), 40)
        self.assertContains(page, "Showing 40 types per page")
        self.assertEqual(len(self.client.get(reverse("item_types:index") + "?page=2").context["item_types"]), 6)

    def test_type_description_limit_and_quota(self):
        url = reverse("item_types:create")
        response = self.client.post(url, {"name": "Too long", "description": "x" * 501})
        self.assertIn("description", response.context["form"].errors)
        self.assertFalse(ItemTypes.objects.filter(name="Too long").exists())
        self.assertEqual(self.client.post(url, {
            "name": "At the limit", "description": "x" * 500,
        }).status_code, 302)

        ItemTypes.objects.bulk_create([
            ItemTypes(owner=self.owner, name=f"Type {number}") for number in range(18)
        ])
        self.assertEqual(ItemTypes.objects.filter(owner=self.owner).count(), 20)
        self.assertContains(self.client.get(url), "up to 20 types")
        self.assertContains(self.client.post(url, {"name": "Extra"}), "up to 20 types")
        self.assertFalse(ItemTypes.objects.filter(owner=self.owner, name="Extra").exists())
        removable = ItemTypes.objects.get(owner=self.owner, name="At the limit")
        self.client.post(reverse("item_types:delete", args=[removable.pk]))
        self.assertEqual(self.client.post(url, {"name": "Replacement"}).status_code, 302)
