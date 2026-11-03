from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class AccountFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Space-for-everyday-428!"
        cls.user = User.objects.create_user(username="alex", password=cls.password)

    def test_landing_has_login_and_signup_links(self):
        response = self.client.get(reverse("landing"))
        self.assertContains(response, reverse("accounts:login"))
        self.assertContains(response, reverse("accounts:signup"))

    def test_signup_hashes_password_and_opens_dashboard(self):
        response = self.client.post(reverse("accounts:signup"), {
            "username": "new-member", "password1": self.password, "password2": self.password,
        })
        self.assertRedirects(response, "/tana")
        member = User.objects.get(username="new-member")
        self.assertNotEqual(member.password, self.password)
        self.assertTrue(member.check_password(self.password))
        self.assertEqual(int(self.client.session["_auth_user_id"]), member.pk)

    def test_signup_rejects_duplicate_username_and_mismatched_or_weak_passwords(self):
        for username, password1, password2 in [
            ("alex", self.password, self.password),
            ("someone", self.password, "different-password"),
            ("someone", "123", "123"),
        ]:
            with self.subTest(username=username, password=password1):
                response = self.client.post(reverse("accounts:signup"), {
                    "username": username, "password1": password1, "password2": password2,
                })
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_login_redirects_to_dashboard_and_persists_session(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "alex", "password": self.password,
        })
        self.assertRedirects(response, "/tana")
        self.assertContains(self.client.get("/tana"), "alex")

    def test_wrong_password_and_inactive_user_are_rejected(self):
        for active, password in [(True, "wrong"), (False, self.password)]:
            self.user.is_active = active
            self.user.save()
            response = self.client.post(reverse("accounts:login"), {
                "username": "alex", "password": password,
            })
            self.assertTrue(response.context["form"].errors)
            self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_rejects_external_next_redirect(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "alex", "password": self.password, "next": "https://example.com/steal",
        })
        self.assertRedirects(response, "/tana")

    def test_authenticated_auth_pages_redirect_to_dashboard(self):
        self.client.force_login(self.user)
        for name in ("accounts:login", "accounts:signup"):
            self.assertRedirects(self.client.get(reverse(name)), "/tana")

    def test_logout_requires_post_and_clears_session(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("accounts:logout")), "/")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.get("/tana"), "/accounts/login/?next=/tana")

    def test_auth_forms_and_logout_enforce_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for name in ("accounts:login", "accounts:signup"):
            self.assertEqual(client.post(reverse(name), {}).status_code, 403)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse("accounts:logout")).status_code, 403)
        response = client.get("/tana")
        token = response.cookies["csrftoken"].value
        self.assertRedirects(client.post(reverse("accounts:logout"), {
            "csrfmiddlewaretoken": token,
        }), "/")
