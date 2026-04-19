from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from subscriptions.models import CustomerSubscription, RecipeUsageMonth
from subscriptions.quota import current_year_month


class RecipePermissionsTests(TestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.user = User.objects.create_user(
            username="tier-user",
            password=self.password,
            email="tier@example.com",
        )
        self.client.login(username=self.user.username, password=self.password)

    def test_favorite_toggle_requires_regular_or_premium(self):
        response = self.client.post(
            reverse("toggle_favorite"),
            data={"recipe_id": "abc", "action": "add", "recipe_data": {"title": "A"}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertEqual(body.get("required_plan"), CustomerSubscription.Plan.REGULAR)

    def test_favorite_toggle_allows_regular(self):
        CustomerSubscription.objects.create(
            user=self.user,
            status=CustomerSubscription.Status.ACTIVE,
            plan=CustomerSubscription.Plan.REGULAR,
        )
        response = self.client.post(
            reverse("toggle_favorite"),
            data={"recipe_id": "abc", "action": "add", "recipe_data": {"title": "A"}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "added")

    @patch("recipes.views.discover_pantry_recipes")
    def test_discovery_api_blocks_when_quota_exhausted(self, discover_mock):
        RecipeUsageMonth.objects.create(
            year_month=current_year_month(),
            user=self.user,
            count=2,
        )
        response = self.client.post(
            reverse("discover_recipes_api"),
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 402)
        discover_mock.assert_not_called()
