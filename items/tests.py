from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Item


class ItemFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alex = get_user_model().objects.create_user(username="alex")
        cls.sam = get_user_model().objects.create_user(username="sam")

    def test_items_page_requires_login(self):
        url = reverse("items:index")
        self.assertRedirects(self.client.get(url), f"/accounts/login/?next={url}")
        self.assertRedirects(self.client.post(url, {"name": "Laptop"}), f"/accounts/login/?next={url}")
        self.assertEqual(Item.objects.count(), 0)

    def test_add_item_and_see_it_on_dashboard(self):
        self.client.force_login(self.alex)
        response = self.client.post(reverse("items:index"), {
            "name": "Laptop", "description": "Everyday computer",
            "notes": "Warranty until next year",
        })
        self.assertRedirects(response, reverse("items:index"))
        item = Item.objects.get()
        self.assertEqual(item.owner, self.alex)
        self.assertEqual(item.description, "Everyday computer")
        self.assertEqual(item.notes, "Warranty until next year")
        self.assertIsNone(item.edited_at)
        self.assertIsNone(item.edited_by)
        self.assertContains(self.client.get(reverse("items:index")), "Laptop")
        self.assertContains(self.client.get(reverse("dashboard:index")), "Laptop")

    def test_empty_name_is_rejected(self):
        self.client.force_login(self.alex)
        response = self.client.post(reverse("items:index"), {"name": "   ", "notes": "Something"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)
        self.assertEqual(Item.objects.count(), 0)

    def test_items_are_private_and_text_is_escaped(self):
        Item.objects.create(owner=self.alex, name="Alex item", description="<script>alert(1)</script>")
        Item.objects.create(owner=self.sam, name="Sam private item")
        self.client.force_login(self.alex)
        page = self.client.get(reverse("items:index"))
        self.assertContains(page, "Alex item")
        self.assertNotContains(page, "Sam private item")
        self.assertNotContains(page, "<script>alert(1)</script>")
        self.assertNotContains(self.client.get(reverse("dashboard:index")), "Sam private item")

    def test_edit_prefills_form_and_saves_description_without_changing_owner(self):
        item = Item.objects.create(owner=self.alex, name="Old name", notes="Keep this note")
        created_at = item.created_at
        self.client.force_login(self.alex)
        url = reverse("items:edit", args=[item.pk])
        page = self.client.get(url)
        self.assertContains(page, 'value="Old name"')
        self.assertContains(page, "Keep this note")
        self.assertRedirects(self.client.post(url, {
            "name": "New name", "description": "My description", "notes": "Keep this note",
        }), reverse("items:index"))
        item.refresh_from_db()
        self.assertEqual(item.name, "New name")
        self.assertEqual(item.description, "My description")
        self.assertEqual(item.notes, "Keep this note")
        self.assertEqual(item.owner, self.alex)
        self.assertEqual(item.created_at, created_at)
        self.assertIsNotNone(item.edited_at)
        self.assertGreaterEqual(item.edited_at, created_at)
        self.assertEqual(item.edited_by, self.alex)
        self.assertContains(self.client.get(reverse("items:index")), "My description")
        self.assertContains(self.client.get(reverse("dashboard:index")), "My description")

    def test_edit_metadata_is_not_in_form_or_page(self):
        item = Item.objects.create(owner=self.alex, name="Original")
        self.client.force_login(self.alex)
        url = reverse("items:edit", args=[item.pk])
        page = self.client.get(url)
        self.assertNotContains(page, 'name="edited_at"')
        self.assertNotContains(page, 'name="edited_by"')
        self.assertRedirects(self.client.post(url, {
            "name": "Updated", "edited_by": self.sam.pk,
            "edited_at": "2001-01-01T00:00:00Z",
        }), reverse("items:index"))
        item.refresh_from_db()
        self.assertEqual(item.edited_by, self.alex)
        self.assertNotEqual(item.edited_at.year, 2001)

    def test_admin_edit_records_administrator(self):
        administrator = get_user_model().objects.create_superuser(
            username="administrator", password="Test-password-347!"
        )
        item = Item.objects.create(owner=self.alex, name="Original")
        self.client.force_login(administrator)
        url = reverse("admin:items_item_change", args=[item.pk])
        response = self.client.post(url, {
            "owner": self.alex.pk, "name": "Updated by admin",
            "description": "", "notes": "", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.name, "Updated by admin")
        self.assertEqual(item.edited_by, administrator)
        self.assertIsNotNone(item.edited_at)

    def test_edit_is_private_for_get_and_post(self):
        item = Item.objects.create(owner=self.sam, name="Sam's item")
        url = reverse("items:edit", args=[item.pk])
        self.assertRedirects(self.client.get(url), f"/accounts/login/?next={url}")
        self.client.force_login(self.alex)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"name": "Stolen"}).status_code, 404)
        item.refresh_from_db()
        self.assertEqual(item.name, "Sam's item")

    def test_invalid_edit_does_not_change_item(self):
        item = Item.objects.create(owner=self.alex, name="Original")
        self.client.force_login(self.alex)
        response = self.client.post(reverse("items:edit", args=[item.pk]), {
            "name": "  ", "description": "Should not save",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)
        item.refresh_from_db()
        self.assertEqual(item.name, "Original")
        self.assertEqual(item.description, "")
        self.assertIsNone(item.edited_at)
        self.assertIsNone(item.edited_by)

    def test_edit_requires_csrf_token(self):
        item = Item.objects.create(owner=self.alex, name="Original")
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alex)
        url = reverse("items:edit", args=[item.pk])
        self.assertEqual(client.post(url, {"name": "Blocked"}).status_code, 403)
        item.refresh_from_db()
        self.assertEqual(item.name, "Original")

    def test_post_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alex)
        self.assertEqual(client.post(reverse("items:index"), {"name": "Blocked"}).status_code, 403)
        self.assertEqual(Item.objects.count(), 0)
        response = client.get(reverse("items:index"))
        token = response.cookies["csrftoken"].value
        self.assertRedirects(client.post(reverse("items:index"), {
            "name": "Allowed", "csrfmiddlewaretoken": token,
        }), reverse("items:index"))
        self.assertEqual(Item.objects.count(), 1)

    def test_navigation_marks_my_tana_as_current(self):
        self.client.force_login(self.alex)
        response = self.client.get(reverse("items:index"))
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, reverse("dashboard:index"))
        self.assertContains(response, "Favorites")
