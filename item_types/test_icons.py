from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from items.models import Item
from .icons import DEFAULT_ICON, ICON_CHOICES
from .models import ItemTypes


class TypeIconTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="icon-user")
        self.client.force_login(self.user)

    def test_defaults_selection_and_validation(self):
        self.assertTrue(32 <= len(ICON_CHOICES) <= 48)
        self.assertContains(self.client.get(reverse("item_types:create")), "Choose a Tana Type icon")
        self.client.post(reverse("item_types:create"), {"name": "Default"})
        self.assertEqual(ItemTypes.objects.get(name="Default").icon, DEFAULT_ICON)
        response = self.client.post(reverse("item_types:create"), {"name": "Camera", "icon": "1F4F7"})
        self.assertEqual(response.status_code, 302)
        kind = ItemTypes.objects.get(name="Camera")
        self.assertEqual(kind.icon, "1F4F7")
        self.client.post(reverse("item_types:edit", args=[kind.pk]), {"name": "Camera", "icon": "1F4DA"})
        kind.refresh_from_db()
        self.assertEqual(kind.icon, "1F4DA")
        response = self.client.post(reverse("item_types:create"), {"name": "Invalid", "icon": "../../other"})
        self.assertIn("icon", response.context["form"].errors)
        self.assertFalse(ItemTypes.objects.filter(name="Invalid").exists())

    def test_icon_appears_on_types_items_and_fallback_is_safe(self):
        kind = ItemTypes.objects.create(owner=self.user, name="Tools", icon="1F527")
        Item.objects.create(owner=self.user, item_type=kind, name="Hammer")
        for url in (reverse("item_types:index"), reverse("items:index"), reverse("dashboard:index")):
            self.assertContains(self.client.get(url), "images/openmoji/1F527.svg")
        kind.icon = "unknown"
        kind.save()
        self.assertContains(self.client.get(reverse("item_types:index")), f"images/openmoji/{DEFAULT_ICON}.svg")
