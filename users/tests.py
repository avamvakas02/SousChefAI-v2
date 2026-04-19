from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from subscriptions.models import CustomerSubscription
from .models import UserProfile


class AccountSettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="chef-alex",
            password="StrongPass123!",
            email="alex@example.com",
        )

    def test_account_settings_requires_authentication(self):
        response = self.client.get(reverse("account_settings"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/login/", response.url)

    def test_account_settings_updates_user_and_profile(self):
        self.client.login(username="chef-alex", password="StrongPass123!")
        response = self.client.post(
            reverse("account_settings"),
            data={
                "first_name": "Alex",
                "last_name": "Cook",
                "username": "chef-alex-updated",
                "email": "alex.updated@example.com",
                "skill_level": UserProfile.SkillLevel.INTERMEDIATE,
            },
        )
        self.assertRedirects(response, reverse("account_settings"))

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Alex")
        self.assertEqual(self.user.last_name, "Cook")
        self.assertEqual(self.user.username, "chef-alex-updated")
        self.assertEqual(self.user.email, "alex.updated@example.com")
        self.assertEqual(self.user.profile.skill_level, UserProfile.SkillLevel.INTERMEDIATE)


class ProfilePermissionsTests(TestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.user = User.objects.create_user(
            username="favorite-user",
            password=self.password,
            email="favorite@example.com",
        )

    def test_profile_redirects_visitor_to_pricing(self):
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.get(reverse("profile"))
        self.assertRedirects(response, reverse("pricing"))

    def test_profile_allows_regular_user(self):
        CustomerSubscription.objects.create(
            user=self.user,
            status=CustomerSubscription.Status.ACTIVE,
            plan=CustomerSubscription.Plan.REGULAR,
        )
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
