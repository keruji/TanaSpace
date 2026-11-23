from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from item_types.models import ItemTypes, ItemTypeProperty
from .models import Item
from .forms import ItemForm


class ItemPropertyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="owner")
        self.other = get_user_model().objects.create_user(username="other")
        self.kind = ItemTypes.objects.create(owner=self.user, name="Electronics", property_schema_version=1)
        self.client.force_login(self.user)
        self.text = self.prop("Brand", "text", required=True)
        self.number = self.prop("Wattage", "number", configuration={"min": 1.1, "max": 1000})
        self.date = self.prop("Purchased", "date")
        self.boolean = self.prop("Warranty", "boolean")
        self.choice = self.prop("Unit", "dropdown", configuration={"options": [{"id": "stable-option", "label": "Each", "archived": False}]})

    def prop(self, name, kind, **kwargs):
        return ItemTypeProperty.objects.create(item_type=self.kind, name=name, data_type=kind, **kwargs)

    def data(self, **kwargs):
        return {"name": "Laptop", "item_type": self.kind.pk, "schema_version": "1",
                "property_" + str(self.text.pk): "ACME", **kwargs}

    def test_all_values_round_trip_and_detail_formatting(self):
        data = self.data(**{"property_" + str(self.number.pk): "15.125", "property_" + str(self.date.pk): "2026-01-02",
                            "property_" + str(self.boolean.pk): "on", "property_" + str(self.choice.pk): "stable-option"})
        self.assertEqual(self.client.post(reverse("items:create"), data).status_code, 302)
        item = Item.objects.get()
        self.assertEqual(item.property_values, {str(self.text.pk): "ACME", str(self.number.pk): 15.125,
                         str(self.date.pk): "2026-01-02", str(self.boolean.pk): True, str(self.choice.pk): "stable-option"})
        response = self.client.get(reverse("items:detail", args=[item.pk]))
        for label in ["ACME", "Jan 2, 2026", "Yes", "Each"]:
            self.assertContains(response, label)
        edit = self.client.get(reverse("items:edit", args=[item.pk]))
        self.assertContains(edit, 'value="15.125"')
        self.assertEqual(self.client.post(reverse("items:edit", args=[item.pk]), self.data()).status_code, 302)
        item.refresh_from_db(); self.assertIs(item.property_values[str(self.boolean.pk)], False)

    def test_validation_retains_values_without_writes(self):
        for prop, value in [(self.text, ""), (self.text, "a" * 1001), (self.number, "NaN"), (self.number, "1.00001"),
                            (self.number, "1001"), (self.date, "2026-02-30"), (self.choice, "foreign-option")]:
            with self.subTest(prop=prop.name, value=value):
                response = self.client.post(reverse("items:create"), self.data(**{"property_" + str(prop.pk): value}), headers={"HX-Request": "true", "HX-Target": "modal-host"})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertNotIn("X-Workspace-Changed", response)
                self.assertEqual(Item.objects.count(), 0)
        form = ItemForm(self.data(**{"property_" + str(self.number.pk): "1.1"}), owner=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_required_boolean_accepts_false_and_requires_explicit_answer(self):
        self.boolean.required = True; self.boolean.save()
        data = self.data(**{"property_" + str(self.boolean.pk): "false"})
        form = ItemForm(data, owner=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIs(form.save(commit=False).property_values[str(self.boolean.pk)], False)
        form = ItemForm(self.data(), owner=self.user)
        self.assertFalse(form.is_valid())

    def test_unknown_archived_and_other_owner_keys_rejected(self):
        archived = self.prop("Old", "text", archived_at=timezone.now())
        for identifier in [str(archived.pk), "not-an-id"]:
            response = self.client.post(reverse("items:create"), self.data(**{"property_" + identifier: "bad"}))
            self.assertContains(response, "unknown or unavailable")
        private = ItemTypes.objects.create(owner=self.other, name="Private")
        self.assertFalse(ItemForm(self.data(item_type=private.pk), owner=self.user).is_valid())

    def test_stale_schema_keeps_database_and_submitted_values(self):
        response = self.client.post(reverse("items:create"), self.data(schema_version="0"))
        self.assertContains(response, "Properties changed")
        self.assertContains(response, 'value="ACME"')
        self.assertEqual(Item.objects.count(), 0)

    def test_archived_values_preserved_until_confirmed_type_change(self):
        archived = self.prop("Old label", "text", archived_at=timezone.now())
        item = Item.objects.create(owner=self.user, item_type=self.kind, name="Laptop", property_values={str(self.text.pk): "ACME", str(archived.pk): "Archived text"})
        url = reverse("items:edit", args=[item.pk])
        self.client.post(url, self.data())
        item.refresh_from_db(); self.assertEqual(item.property_values[str(archived.pk)], "Archived text")
        destination = ItemTypes.objects.create(owner=self.user, name="Books", property_schema_version=1)
        author = ItemTypeProperty.objects.create(item_type=destination, name="Author", data_type="text", required=True)
        data = {"name": "Laptop", "item_type": destination.pk, "schema_version": "1", "property_" + str(author.pk): "Writer"}
        self.assertEqual(self.client.post(url, data).status_code, 200)
        item.refresh_from_db(); self.assertEqual(item.item_type_id, self.kind.pk)
        self.assertEqual(self.client.post(url, {**data, "confirm_type_change": "on", "property_" + str(author.pk): ""}).status_code, 200)
        item.refresh_from_db(); self.assertIn(str(archived.pk), item.property_values)
        self.assertEqual(self.client.post(url, {**data, "confirm_type_change": "on"}).status_code, 302)
        item.refresh_from_db(); self.assertEqual(item.property_values, {str(author.pk): "Writer"})
        self.assertEqual(item.item_type_id, destination.pk)

    def test_fragment_loading_is_private_non_mutating_and_has_no_shell(self):
        response = self.client.post(reverse("items:custom_fields"), {"item_type": self.kind.pk})
        self.assertContains(response, "Brand")
        self.assertNotContains(response, "<header")
        self.assertNotContains(response, "This field is required")
        self.assertEqual(Item.objects.count(), 0)
        private = ItemTypes.objects.create(owner=self.other, name="Private")
        private_item = Item.objects.create(owner=self.other, item_type=private, name="Private")
        self.assertEqual(self.client.post(reverse("items:custom_fields"), {"item_type": self.kind.pk, "_item_id": private_item.pk}).status_code, 404)
        self.assertEqual(self.client.post(reverse("items:custom_fields"), {"item_type": self.kind.pk, "_item_id": "invalid"}).status_code, 400)
        self.assertEqual(self.client.post(reverse("items:custom_fields"), {"item_type": private.pk}).status_code, 400)
        self.assertEqual(self.client.get(reverse("items:custom_fields")).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True); csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(reverse("items:custom_fields"), {"item_type": self.kind.pk}).status_code, 403)

    def test_no_js_load_then_save_preserves_core_fields(self):
        response = self.client.post(reverse("items:create"), {"name": "Draft", "item_type": self.kind.pk, "notes": "Keep me", "_action": "load_properties"})
        self.assertContains(response, 'value="Draft"')
        self.assertContains(response, "Keep me")
        self.assertNotContains(response, "This field is required")
        self.assertEqual(Item.objects.count(), 0)
        self.assertEqual(self.client.post(reverse("items:create"), self.data(name="Draft", notes="Keep me")).status_code, 302)

    def test_dropdown_retired_selection_can_stay_but_not_be_newly_selected(self):
        self.choice.configuration["options"][0]["archived"] = True; self.choice.save()
        item = Item.objects.create(owner=self.user, item_type=self.kind, name="Old", property_values={str(self.choice.pk): "stable-option"})
        data = self.data(**{"property_" + str(self.choice.pk): "stable-option"})
        self.assertFalse(ItemForm(data, owner=self.user).is_valid())
        form = ItemForm(data, instance=item, owner=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_labels_and_values_are_escaped(self):
        self.text.name = "<script>bad()</script>"; self.text.save()
        item = Item.objects.create(owner=self.user, item_type=self.kind, name="Safe", property_values={str(self.text.pk): "<img src=x onerror=bad()>"})
        response = self.client.get(reverse("items:detail", args=[item.pk]))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>bad()")
        self.assertNotContains(response, "<img src=x")


class AdditiveSchemaCompatibilityTests(TestCase):
    def test_historical_models_can_insert_against_expanded_schema(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        old = executor.loader.project_state([
            ("accounts", "0003_user_nickname"),
            ("item_types", "0002_alter_itemtypes_description"),
            ("items", "0007_item_is_favorite"),
        ]).apps
        user = old.get_model("accounts", "User").objects.create(username="old-release")
        kind = old.get_model("item_types", "ItemTypes").objects.create(owner_id=user.pk, name="Old type")
        item = old.get_model("items", "Item").objects.create(owner_id=user.pk, item_type_id=kind.pk, name="Old item")
        self.assertEqual(Item.objects.get(pk=item.pk).property_values, {})
        self.assertEqual(ItemTypes.objects.get(pk=kind.pk).property_schema_version, 0)
        self.assertFalse(get_user_model().objects.get(pk=user.pk).is_development_demo)
