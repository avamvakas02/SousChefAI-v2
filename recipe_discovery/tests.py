from unittest.mock import patch

import json
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from pantry.models import PantryItem
from subscriptions import quota
from subscriptions.models import CustomerSubscription, RecipeUsageMonth
from users.models import UserProfile

from .models import SavedRecipe
from .recipe_ingredients import filter_household_staples, is_household_staple
from .services.gemini_recipes import (
    _difficulty_mix_for_skill,
    _extract_json_object,
    _gemini_generate_recipe_cards,
    _slugify_recipe_id,
)


class HouseholdStapleIngredientTests(SimpleTestCase):
    def test_filters_household_staples_from_recipe_requirements(self):
        ingredients = ["Chicken", "Water", "Kosher salt", "Bell pepper", "Black pepper"]

        self.assertEqual(filter_household_staples(ingredients), ["Chicken", "Bell pepper"])

    def test_does_not_filter_named_foods_that_include_water(self):
        self.assertFalse(is_household_staple("Coconut water"))


class GeminiRecipeJsonExtractionTests(SimpleTestCase):
    def test_extracts_json_from_fenced_response(self):
        payload = _extract_json_object(
            '```json\n{"recipes":[{"title":"Tomato Pasta"}]}\n```'
        )

        self.assertEqual(payload["recipes"][0]["title"], "Tomato Pasta")

    def test_extracts_json_with_surrounding_text(self):
        payload = _extract_json_object(
            'Here are recipes:\n{"recipes":[{"title":"Salmon Rice"}]}\nEnjoy!'
        )

        self.assertEqual(payload["recipes"][0]["title"], "Salmon Rice")

    def test_wraps_top_level_recipe_array(self):
        payload = _extract_json_object('[{"title":"Chicken Skillet"}]')

        self.assertEqual(payload["recipes"][0]["title"], "Chicken Skillet")


class RecipeDifficultyMixTests(SimpleTestCase):
    def test_returns_skill_based_difficulty_mix(self):
        self.assertEqual(
            _difficulty_mix_for_skill(UserProfile.SkillLevel.BEGINNER),
            ["Easy", "Easy", "Easy", "Medium"],
        )
        self.assertEqual(
            _difficulty_mix_for_skill(UserProfile.SkillLevel.INTERMEDIATE),
            ["Easy", "Medium", "Medium", "Hard"],
        )
        self.assertEqual(
            _difficulty_mix_for_skill(UserProfile.SkillLevel.ADVANCED),
            ["Easy", "Medium", "Hard", "Hard"],
        )

    def test_recipe_ids_are_ascii_slugs(self):
        self.assertEqual(
            _slugify_recipe_id("Gourmet Salmon with Herb Rice Sautéed Veggies", 1),
            "gourmet-salmon-with-herb-rice-sauteed-veggies",
        )


class GeminiRecipeGenerationTests(SimpleTestCase):
    @override_settings(GEMINI_API_KEY="test-key", GEMINI_RECIPE_MODEL="gemini-test")
    @patch("recipe_discovery.services.gemini_recipes._persist_generated_recipe_image", return_value="/media/test.png")
    @patch("recipe_discovery.services.gemini_recipes.urlopen")
    def test_recipe_request_asks_gemini_for_json(self, mock_urlopen, mock_image):
        gemini_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "recipes": [
                                            {
                                                "title": "Tomato Pasta",
                                                "description": "A quick tomato pasta.",
                                                "time_minutes": 20,
                                                "difficulty": "Easy",
                                                "portions": 2,
                                                "needed": ["Tomato", "Pasta"],
                                                "steps": ["Boil pasta", "Make sauce"],
                                            }
                                        ]
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
            gemini_payload
        ).encode("utf-8")

        cards, error = _gemini_generate_recipe_cards(["Tomato", "Pasta"], "quick")

        self.assertIsNone(error)
        self.assertEqual(cards[0]["title"], "Tomato Pasta")
        request = mock_urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        prompt = body["contents"][0]["parts"][0]["text"]
        self.assertIn(
            "Match this exact difficulty sequence for the 4 recipes: Easy, Easy, Easy, Medium",
            prompt,
        )
        self.assertEqual(mock_image.call_count, 1)


class RecipeDiscoveryPermissionTests(TestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.user = User.objects.create_user(
            username="recipe-user",
            password=self.password,
            email="recipe@example.com",
        )

    def _login_with_pantry(self):
        PantryItem.objects.create(
            user=self.user,
            name="Tomato",
            category=PantryItem.Category.PRODUCE,
        )
        self.client.login(username=self.user.username, password=self.password)

    @staticmethod
    def _recipe_payload():
        return {
            "id": "tomato-pasta",
            "title": "Tomato Pasta",
            "description": "A quick tomato pasta.",
            "image_url": "/static/images/hero-image.jpg",
            "time_minutes": 20,
            "difficulty": "Easy",
            "portions": 2,
            "pantry_match": 80,
            "needed": ["Tomato", "Pasta"],
            "steps": ["Boil pasta", "Make sauce"],
        }

    @staticmethod
    def _alternate_recipe_payload():
        return {
            "id": "tomato-soup",
            "title": "Tomato Soup",
            "description": "A cozy tomato soup.",
            "image_url": "/static/images/hero-image.jpg",
            "time_minutes": 25,
            "difficulty": "Easy",
            "portions": 2,
            "pantry_match": 75,
            "needed": ["Tomato", "Onion"],
            "steps": ["Simmer tomatoes", "Blend soup"],
        }

    @patch("recipe_discovery.views._gemini_generate_recipe_cards")
    def test_visitor_recipe_generation_stops_at_monthly_quota(self, mock_generate):
        self._login_with_pantry()
        mock_generate.return_value = ([self._recipe_payload()], None)

        for _ in range(2):
            response = self.client.post(reverse("recipe_discovery"))
            self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse("recipe_discovery"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_generate.call_count, 2)
        row = RecipeUsageMonth.objects.get(
            user=self.user,
            year_month=quota.current_year_month(),
        )
        self.assertEqual(row.count, 2)

    @patch("recipe_discovery.views._gemini_generate_recipe_cards")
    def test_empty_pantry_does_not_consume_recipe_quota(self, mock_generate):
        self.client.login(username=self.user.username, password=self.password)

        response = self.client.post(reverse("recipe_discovery"))

        self.assertEqual(response.status_code, 200)
        mock_generate.assert_not_called()
        row = RecipeUsageMonth.objects.get(
            user=self.user,
            year_month=quota.current_year_month(),
        )
        self.assertEqual(row.count, 0)

    @patch("recipe_discovery.views._gemini_generate_recipe_cards")
    def test_recipe_generation_uses_profile_skill_level(self, mock_generate):
        self._login_with_pantry()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.skill_level = UserProfile.SkillLevel.ADVANCED
        profile.save(update_fields=["skill_level", "updated_at"])
        mock_generate.return_value = ([self._recipe_payload()], None)

        response = self.client.post(reverse("recipe_discovery"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_generate.call_args.args[2], UserProfile.SkillLevel.ADVANCED)

    @patch("recipe_discovery.views._gemini_generate_recipe_cards")
    def test_recipe_regeneration_is_limited_to_two_attempts(self, mock_generate):
        self._login_with_pantry()
        CustomerSubscription.objects.create(
            user=self.user,
            status=CustomerSubscription.Status.ACTIVE,
            plan=CustomerSubscription.Plan.PREMIUM,
        )
        mock_generate.return_value = ([self._alternate_recipe_payload()], None)
        session = self.client.session
        session["recipe_discovery_cards"] = [self._recipe_payload()]
        session["recipe_discovery_goal"] = "quick dinner"
        session.save()

        for _ in range(2):
            response = self.client.post(
                reverse("recipe_discovery"),
                {"action": "regenerate"},
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("recipe_discovery"),
            {"action": "regenerate"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_generate.call_count, 2)
        session = self.client.session
        self.assertEqual(session["recipe_discovery_regenerate_count"], 2)
        self.assertEqual(
            session["recipe_discovery_cards"][0]["title"],
            "Tomato Soup",
        )
        self.assertIn("Fresh alternate set", mock_generate.call_args.args[1])
        self.assertContains(response, "Regenerate Recipes")

    def test_saving_recipe_requires_premium_plan(self):
        self.client.login(username=self.user.username, password=self.password)
        session = self.client.session
        session["recipe_discovery_cards"] = [self._recipe_payload()]
        session.save()

        response = self.client.post(reverse("save_recipe", args=["tomato-pasta"]))

        self.assertRedirects(response, reverse("pricing"))
        self.assertFalse(SavedRecipe.objects.filter(user=self.user).exists())

    def test_premium_user_can_save_recipe(self):
        CustomerSubscription.objects.create(
            user=self.user,
            status=CustomerSubscription.Status.ACTIVE,
            plan=CustomerSubscription.Plan.PREMIUM,
        )
        self.client.login(username=self.user.username, password=self.password)
        session = self.client.session
        session["recipe_discovery_cards"] = [self._recipe_payload()]
        session.save()

        response = self.client.post(reverse("save_recipe", args=["tomato-pasta"]))

        self.assertRedirects(response, reverse("saved_recipes"))
        self.assertTrue(SavedRecipe.objects.filter(user=self.user).exists())
