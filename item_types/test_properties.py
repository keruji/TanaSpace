import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from items.models import Item
from .models import ItemTypes, ItemTypeProperty


class PropertyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="owner")
        self.other = get_user_model().objects.create_user(username="other")
        self.kind = ItemTypes.objects.create(owner=self.user, name="Electronics")
        self.client.force_login(self.user)

    def data(self, **kwargs):
        self.kind.refresh_from_db()
        return {"name": "Brand", "data_type": "text", "schema_version": self.kind.property_schema_version, **kwargs}

    def create(self, **kwargs):
        return self.client.post(reverse("item_types:property_create", args=[self.kind.pk]), self.data(**kwargs))

    def edit(self, prop, **kwargs):
        return self.client.post(reverse("item_types:property_edit", args=[self.kind.pk, prop.pk]), self.data(**kwargs))

    def test_creation_rename_required_and_case_insensitive_names(self):
        self.assertEqual(self.create().status_code, 302)
        prop = self.kind.properties.get()
        identifier = prop.pk
        item = Item.objects.create(owner=self.user, item_type=self.kind, name="Laptop", property_values={str(identifier): "ACME"})
        self.assertEqual(self.edit(prop, name="Manufacturer", required="on").status_code, 302)
        prop.refresh_from_db(); item.refresh_from_db()
        self.assertEqual(prop.pk, identifier)
        self.assertTrue(prop.required)
        self.assertEqual(item.property_values[str(identifier)], "ACME")
        response = self.create(name="manufacturer")
        self.assertContains(response, "already uses this name")
        self.assertEqual(self.kind.properties.count(), 1)

    def test_required_warning_and_no_silent_backfill(self):
        item = Item.objects.create(owner=self.user, item_type=self.kind, name="Old item")
        self.create(required="on")
        self.assertContains(self.client.get(reverse("item_types:edit", args=[self.kind.pk])), "1 item need required property values")
        item.refresh_from_db()
        self.assertEqual(item.property_values, {})

    def test_archive_retains_values_and_disappears_from_forms(self):
        self.create()
        prop = self.kind.properties.get()
        item = Item.objects.create(owner=self.user, item_type=self.kind, name="Laptop", property_values={str(prop.pk): "Old brand"})
        url = reverse("item_types:property_archive", args=[self.kind.pk, prop.pk])
        self.client.get(url)
        prop.refresh_from_db(); self.assertIsNone(prop.archived_at)
        self.assertContains(self.client.post(url, self.data()), "Confirm that")
        response = self.client.post(url, self.data(confirm_archive="yes"))
        self.assertEqual(response.status_code, 302)
        prop.refresh_from_db(); self.assertIsNotNone(prop.archived_at)
        item.refresh_from_db(); self.assertEqual(item.property_values[str(prop.pk)], "Old brand")
        self.assertContains(self.client.get(reverse("items:detail", args=[item.pk])), "Old brand")
        self.assertNotContains(self.client.get(reverse("items:edit", args=[item.pk])), 'name="property_' + str(prop.pk) + '"')

    def test_order_and_stale_mutations(self):
        self.create(name="First"); self.create(name="Second")
        first, second = list(self.kind.properties.all())
        url = reverse("item_types:property_reorder", args=[self.kind.pk, second.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, self.data(direction="up")).status_code, 302)
        self.assertEqual(list(self.kind.properties.values_list("pk", flat=True)), [second.pk, first.pk])
        self.assertEqual(self.client.post(url, {"schema_version": 0, "direction": "down"}).status_code, 400)
        self.assertContains(self.edit(second, schema_version=0), "changed in another window")

    def test_delete_property_removes_values_only_after_confirmation(self):
        self.create()
        prop = self.kind.properties.get()
        item = Item.objects.create(owner=self.user, item_type=self.kind, name="Laptop", property_values={str(prop.pk): "ACME", "other": "keep"})
        url = reverse("item_types:property_delete", args=[self.kind.pk, prop.pk])
        self.assertContains(self.client.get(url), "permanently deletes")
        self.assertContains(self.client.post(url, self.data()), "Confirm that")
        self.assertContains(self.client.post(url, {"schema_version": 0, "confirm_delete": "yes"}), "Properties changed")
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, self.data(confirm_delete="yes")).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(url, self.data(confirm_delete="yes")).status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.property_values, {"other": "keep"})
        self.assertFalse(self.kind.properties.filter(pk=prop.pk).exists())

    def test_type_changes_block_zero_and_false_but_allow_unused(self):
        self.create(data_type="boolean")
        prop = self.kind.properties.get()
        item = Item.objects.create(owner=self.user, item_type=self.kind, name="Saved", property_values={str(prop.pk): False})
        self.assertContains(self.edit(prop, data_type="number"), "cannot change")
        item.property_values = {str(prop.pk): 0}; item.save()
        self.assertContains(self.edit(prop, data_type="number"), "cannot change")
        item.property_values = {}; item.save()
        self.assertEqual(self.edit(prop, data_type="number").status_code, 302)

    def test_numeric_bounds_and_precision(self):
        self.assertContains(self.create(data_type="number", minimum="10", maximum="2"), "Maximum must")
        self.assertContains(self.create(data_type="number", minimum="NaN"), "Enter a number")
        self.assertEqual(self.create(data_type="number", minimum="1.1", maximum="10").status_code, 302)
        prop = self.kind.properties.get()
        Item.objects.create(owner=self.user, item_type=self.kind, name="Saved", property_values={str(prop.pk): 4.5})
        response = self.edit(prop, data_type="number", maximum="4")
        self.assertEqual(response.status_code, 200)
        prop.refresh_from_db(); self.assertEqual(prop.configuration["max"], 10)

    def option_data(self, entries):
        data = {"data_type": "dropdown", "options-TOTAL_FORMS": len(entries), "options-INITIAL_FORMS": len(entries)}
        for index, entry in enumerate(entries):
            data.update({f"options-{index}-{key}": value for key, value in entry.items()})
        return data

    def test_dropdown_stable_option_ids_and_archiving(self):
        self.create(**self.option_data([{"label": "Each"}, {"label": "Pack"}]))
        prop = self.kind.properties.get()
        options = prop.configuration["options"]
        saved_id = options[0]["id"]
        options[0]["label"] = "Single"
        options[0]["archived"] = "on"
        self.assertEqual(self.edit(prop, **self.option_data(options)).status_code, 302)
        prop.refresh_from_db(); self.assertEqual(prop.configuration["options"][0]["id"], saved_id)
        self.assertTrue(prop.configuration["options"][0]["archived"])
        self.assertContains(self.edit(prop, **self.option_data(options[1:])), "cannot be deleted")
        options[1]["id"] = str(uuid.uuid4())
        self.assertContains(self.edit(prop, **self.option_data(options)), "identifier is invalid")

    def test_dropdown_duplicates_and_missing_management_form(self):
        self.assertEqual(self.create(data_type="dropdown").status_code, 200)
        self.assertContains(self.create(**self.option_data([{"label": "Each"}, {"label": "each"}])), "must be unique")
        self.assertEqual(self.kind.properties.count(), 0)

    def test_cross_account_definition_access(self):
        self.create(); prop = self.kind.properties.get()
        self.client.force_login(self.other)
        for name, args in [("property_create", [self.kind.pk]), ("property_edit", [self.kind.pk, prop.pk]), ("property_archive", [self.kind.pk, prop.pk]), ("property_reorder", [self.kind.pk, prop.pk])]:
            self.assertEqual(self.client.post(reverse("item_types:" + name, args=args), self.data(direction="up")).status_code, 404)
        self.assertEqual(self.kind.properties.count(), 1)

    def test_property_limit(self):
        ItemTypeProperty.objects.bulk_create([ItemTypeProperty(item_type=self.kind, name=f"Field {i}", data_type="text") for i in range(20)])
        self.assertContains(self.create(), "20 active properties")
        self.assertEqual(self.kind.properties.count(), 20)

    def test_total_definition_limit_includes_archived_and_csrf_is_required(self):
        from django.test import Client
        from django.utils import timezone
        ItemTypeProperty.objects.bulk_create([ItemTypeProperty(item_type=self.kind, name=f"Archived {i}", data_type="text", archived_at=timezone.now()) for i in range(50)])
        self.assertContains(self.create(), "50 total")
        client = Client(enforce_csrf_checks=True); client.force_login(self.user)
        self.assertEqual(client.post(reverse("item_types:property_create", args=[self.kind.pk]), self.data()).status_code, 403)

    def test_property_type_is_allowlisted(self):
        self.assertEqual(self.create(data_type="expression").status_code, 200)
        self.assertEqual(self.kind.properties.count(), 0)
