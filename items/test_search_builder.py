from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from item_types.models import ItemTypes, ItemTypeProperty
from .models import Item


class SearchBuilderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="searcher")
        self.client.force_login(self.user)
        self.first = ItemTypes.objects.create(owner=self.user, name="Devices")
        self.second = ItemTypes.objects.create(owner=self.user, name="Tools")
        self.serial1 = ItemTypeProperty.objects.create(item_type=self.first, name="Serial Number", data_type="text")
        self.serial2 = ItemTypeProperty.objects.create(item_type=self.second, name="serial number", data_type="text")
        self.one = Item.objects.create(owner=self.user, item_type=self.first, name="Camera", description="Travel",
                                       property_values={str(self.serial1.pk): "ABC-1"})
        self.two = Item.objects.create(owner=self.user, item_type=self.second, name="Tripod", description="Travel",
                                       property_values={str(self.serial2.pk): "ABC-2"})

    def test_multiple_values_and_shared_property(self):
        response = self.client.get(reverse("items:index"), {
            "search_mode": "builder", "name": ["Camera", "Tripod"], "description": "travel",
            "types": [self.first.pk, self.second.pk], "prop_" + str(self.serial1.pk): "abc",
        })
        self.assertEqual({item.pk for item in response.context["items"]}, {self.one.pk, self.two.pk})
        self.assertFalse(response.context["search_builder"]["errors"])

    def test_unshared_and_private_properties_are_rejected(self):
        private_user = get_user_model().objects.create_user(username="private")
        private_type = ItemTypes.objects.create(owner=private_user, name="Private")
        private = ItemTypeProperty.objects.create(item_type=private_type, name="Secret", data_type="text")
        for prop in (private, ItemTypeProperty.objects.create(item_type=self.first, name="Unique", data_type="text")):
            response = self.client.get(reverse("items:index"), {
                "search_mode": "builder", "types": [self.first.pk, self.second.pk],
                "prop_" + str(prop.pk): "x",
            })
            self.assertTrue(response.context["search_builder"]["errors"])
            self.assertEqual(len(response.context["items"]), 0)

    def test_date_range_and_legacy_search(self):
        date = timezone.localtime(self.one.created_at).date().isoformat()
        response = self.client.get(reverse("items:index"), {"created_from": date, "created_to": date})
        self.assertEqual(len(response.context["items"]), 2)
        response = self.client.get(reverse("items:index"), {"q": "Travel"})
        self.assertEqual(len(response.context["items"]), 2)

    def test_shared_dropdown_values_and_incompatible_types(self):
        first = ItemTypeProperty.objects.create(item_type=self.first, name="Unit", data_type="dropdown", configuration={"options": [{"id": "first", "label": "Each"}]})
        second = ItemTypeProperty.objects.create(item_type=self.second, name="unit", data_type="dropdown", configuration={"options": [{"id": "second", "label": "Each"}]})
        self.one.property_values[str(first.pk)] = "first"
        self.one.save()
        self.two.property_values[str(second.pk)] = "second"
        self.two.save()
        params = {"types": [self.first.pk, self.second.pk], "prop_" + str(first.pk): "each"}
        response = self.client.get(reverse("items:index"), params)
        self.assertEqual({item.pk for item in response.context["items"]}, {self.one.pk, self.two.pk})
        second.data_type = "text"
        second.save()
        response = self.client.get(reverse("items:index"), params)
        self.assertTrue(response.context["search_builder"]["errors"])
        self.assertEqual(len(response.context["items"]), 0)
