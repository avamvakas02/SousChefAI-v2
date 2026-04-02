from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .ingredient_service import (
    clear_catalog_cache,
    get_catalog,
    lookup_preset,
    themealdb_ingredient_image_url,
    themealdb_ingredient_slug,
)
from .views import _presets_for_zone
from .models import PantryItem
from .presets import QUICK_ZONES, get_icon, get_preset, get_zone_by_slug

User = get_user_model()


class ThemealdbImageTests(TestCase):
    def test_slug_spaces_to_underscores(self):
        self.assertEqual(themealdb_ingredient_slug("Chicken Breast"), "chicken_breast")

    def test_slug_strips_diacritics(self):
        # TheMealDB thumbnail filenames are ASCII; slugging should match.
        self.assertEqual(themealdb_ingredient_slug("Crème fraîche"), "creme_fraiche")

    def test_slug_collapse_punctuation_and_underscores(self):
        # TheMealDB thumbnail naming preserves punctuation like '-' and ','.
        self.assertEqual(
            themealdb_ingredient_slug("Free-range Egg, Beaten"),
            "free-range_egg,_beaten",
        )

    def test_image_url_small(self):
        url = themealdb_ingredient_image_url("Lime", size="small")
        self.assertIn("images/ingredients", url)
        self.assertTrue(url.endswith("lime-small.png"))


class IngredientServiceTests(TestCase):
    def tearDown(self):
        clear_catalog_cache()

    @patch("pantry.ingredient_service._fetch_themealdb", return_value=None)
    def test_catalog_fallback_static(self, _mock_fetch):
        c = get_catalog()
        self.assertEqual(c["source"], "static")
        self.assertGreater(len(c["zones"]), 0)
        self.assertIn("tomatoes", c["lookup"])

    @patch("pantry.ingredient_service._fetch_themealdb")
    def test_catalog_from_themealdb_sample(self, mock_fetch):
        mock_fetch.return_value = [
            {"idIngredient": "1", "strIngredient": "Chicken"},
            {"idIngredient": "2", "strIngredient": "Tomato"},
        ]
        clear_catalog_cache()
        c = get_catalog()
        self.assertEqual(c["source"], "themealdb")
        self.assertTrue(any(k.startswith("tmdb_") for k in c["lookup"]))
        parsed = lookup_preset("tmdb_1")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[1], "Chicken")


class PantryPresetsTests(TestCase):
    def test_every_zone_key_maps(self):
        for zone in QUICK_ZONES:
            for key in zone["keys"]:
                parsed = get_preset(key)
                self.assertIsNotNone(parsed, msg=f"missing preset: {key}")
                category, name = parsed
                self.assertTrue(name)

    def test_get_preset_unknown(self):
        self.assertIsNone(get_preset("not_a_real_key"))

    def test_get_zone_by_slug(self):
        z = get_zone_by_slug("produce")
        self.assertIsNotNone(z)
        self.assertEqual(z["title"], "Produce")
        self.assertIsNone(get_zone_by_slug("nope"))

    def test_get_icon(self):
        self.assertTrue(get_icon("tomatoes").startswith("bi-"))
        self.assertEqual(get_icon("unknown_key_xyz"), "bi-basket2")


class PantryZonePresetsTests(TestCase):
    def test_presets_for_zone_dedupes_by_name(self):
        user = User.objects.create_user(
            username="demo",
            email="demo@example.com",
            password="testpass123",
        )
        zone = {"slug": "produce", "keys": ["k1", "k2"]}

        with patch("pantry.views.lookup_preset") as mock_lookup, patch(
            "pantry.views.resolve_icon",
            return_value="bi-basket2",
        ), patch(
            "pantry.views.ingredient_image_url",
            return_value="https://example.com/img.png",
        ):
            # Both keys resolve to the same display name.
            mock_lookup.side_effect = [
                ("cat", "Same Ingredient"),
                ("cat", "Same Ingredient"),
            ]
            presets = _presets_for_zone(user, zone)

        self.assertEqual(len(presets), 1)
        self.assertEqual(presets[0]["name"], "Same Ingredient")
        self.assertFalse(presets[0]["already_added"])

    def test_presets_for_zone_dedupes_by_image_url(self):
        user = User.objects.create_user(
            username="demo2",
            email="demo2@example.com",
            password="testpass123",
        )
        zone = {"slug": "produce", "keys": ["k1", "k2"]}

        with patch("pantry.views.lookup_preset") as mock_lookup, patch(
            "pantry.views.resolve_icon",
            return_value="bi-basket2",
        ), patch(
            "pantry.views.ingredient_image_url",
            side_effect=["https://example.com/same.png", "https://example.com/same.png"],
        ):
            # Names differ, but the image URL resolves to the same thumbnail.
            mock_lookup.side_effect = [
                ("cat", "Ingredient A"),
                ("cat", "Ingredient B"),
            ]
            presets = _presets_for_zone(user, zone)

        self.assertEqual(len(presets), 1)


class PantryItemModelTests(TestCase):
    def test_create_and_str(self):
        user = User.objects.create_user(
            username="pat",
            email="pat@example.com",
            password="testpass123",
        )
        item = PantryItem.objects.create(
            user=user,
            name="Olive oil",
            category=PantryItem.Category.PANTRY,
            quantity="500 ml",
        )
        self.assertIn("Olive oil", str(item))
        self.assertEqual(item.user, user)


class PantryInventoryAjaxDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="invajax",
            email="invajax@example.com",
            password="testpass123",
        )
        self.item = PantryItem.objects.create(
            user=self.user,
            name="Ajax Lime",
            category=PantryItem.Category.PRODUCE,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def _csrf_token(self):
        r = self.client.get(reverse("pantry"))
        self.assertEqual(r.status_code, 200)
        return self.client.cookies["csrftoken"].value

    def test_ajax_single_delete_returns_json_with_removed_id(self):
        token = self._csrf_token()
        r = self.client.post(
            reverse("pantry"),
            {
                "csrfmiddlewaretoken": token,
                "action": "delete",
                "item_id": str(self.item.pk),
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["ok"], True)
        self.assertEqual(r.json()["removed_id"], self.item.pk)
        self.assertEqual(PantryItem.objects.filter(pk=self.item.pk).count(), 0)

    def test_ajax_single_delete_bad_id_returns_json_not_500(self):
        token = self._csrf_token()
        r = self.client.post(
            reverse("pantry"),
            {
                "csrfmiddlewaretoken": token,
                "action": "delete",
                "item_id": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["ok"], False)
        self.assertEqual(PantryItem.objects.filter(pk=self.item.pk).count(), 1)

    def test_ajax_bulk_delete_json_via_accept_header(self):
        """JSON response when Accept: application/json (some proxies strip X-Requested-With)."""
        token = self._csrf_token()
        item2 = PantryItem.objects.create(
            user=self.user,
            name="Ajax Two",
            category=PantryItem.Category.PRODUCE,
        )
        r = self.client.post(
            reverse("pantry"),
            {
                "csrfmiddlewaretoken": token,
                "action": "delete_bulk",
                "item_id": [str(self.item.pk), str(item2.pk)],
            },
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(set(body["removed_ids"]), {self.item.pk, item2.pk})
        self.assertEqual(PantryItem.objects.filter(user=self.user).count(), 0)
