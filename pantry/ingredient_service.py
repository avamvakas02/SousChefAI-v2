"""
Ingredient catalogs: fetch from TheMealDB public API, classify into zones, cache.

Docs: https://www.themealdb.com/api.php
Fallback: local presets in pantry.presets when the API is unreachable.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

from .models import PantryItem
from . import presets as presets_mod

logger = logging.getLogger(__name__)

CACHE_KEY = "pantry.ingredient_catalog.v2"
CACHE_TTL = 60 * 60 * 24  # 24 hours

THEMEALDB_LIST_URL = getattr(
    settings,
    "PANTRY_INGREDIENT_LIST_URL",
    "https://www.themealdb.com/api/json/v1/1/list.php?i=list",
)
MAX_PER_ZONE = getattr(settings, "PANTRY_MAX_INGREDIENTS_PER_ZONE", 100)

# Keyword routing (substring match on lowercased name)
_PRODUCE_KW = (
    "tomato",
    "lettuce",
    "onion",
    "garlic",
    "potato",
    "carrot",
    "apple",
    "banana",
    "lemon",
    "lime",
    "pepper",
    "mushroom",
    "spinach",
    "kale",
    "broccoli",
    "cabbage",
    "avocado",
    "celery",
    "cucumber",
    "eggplant",
    "ginger",
    "orange",
    "grape",
    "melon",
    "mango",
    "pear",
    "peach",
    "cherry",
    "berry",
    "squash",
    "pumpkin",
    "beet",
    "radish",
    "turnip",
    "asparagus",
    "cauliflower",
    "leek",
    "zucchini",
    "parsley",
    "basil",
    "cilantro",
    "mint",
    "chard",
    "arugula",
    "endive",
    "fennel",
    "okra",
    "sprout",
    "watercress",
    "corn",
    "peas",
    "fruit",
    "herb",
    "rocket",
    "scallion",
    "shallot",
)

_DAIRY_MEAT_KW = (
    "milk",
    "cheese",
    "cream",
    "yogurt",
    "butter",
    "egg",
    "chicken",
    "beef",
    "pork",
    "salmon",
    "fish",
    "meat",
    "shrimp",
    "turkey",
    "duck",
    "bacon",
    "lamb",
    "tofu",
    "ham",
    "cod",
    "tuna",
    "steak",
    "sausage",
    "prawn",
    "mussel",
    "oyster",
    "squid",
    "crab",
    "lobster",
    "anchovy",
    "sardine",
    "trout",
    "veal",
    "ghee",
    "mozzarella",
    "cheddar",
    "parmesan",
    "feta",
    "ricotta",
    "paneer",
    "mascarpone",
    "provolone",
    "goat cheese",
)

_PANTRY_KW = (
    "oil",
    "rice",
    "pasta",
    "flour",
    "sugar",
    "salt",
    "pepper",
    "stock",
    "vinegar",
    "sauce",
    "bean",
    "lentil",
    "noodle",
    "bread",
    "oat",
    "honey",
    "molasses",
    "soy",
    "sesame",
    "coconut",
    "cornmeal",
    "baking",
    "yeast",
    "cocoa",
    "coffee",
    "tea",
    "wine",
    "water",
    "syrup",
    "starch",
    "cumin",
    "paprika",
    "curry",
    "oregano",
    "thyme",
    "nutmeg",
    "cinnamon",
    "clove",
    "cardamom",
    "tortilla",
    "cracker",
    "cereal",
    "barley",
    "quinoa",
    "couscous",
    "bulgur",
    "wheat",
    "semolina",
    "masala",
    "chili",
    "ketchup",
    "mustard",
    "mayo",
    "worcestershire",
    "tabasco",
    "salsa",
    "jam",
    "marmalade",
    "gelatin",
    "polenta",
    "cornflour",
    "cornstarch",
    "nori",
    "biscuit",
    "panko",
    "breadcrumb",
    "miso",
    "tahini",
    "sake",
    "sherry",
    "vanilla",
    "extract",
    "garam",
    "walnut",
    "almond",
    "pecan",
    "cashew",
    "peanut",
    "hazelnut",
)

_ZONE_META = [
    {
        "slug": "produce",
        "title": "Produce",
        "subtitle": "Fresh fruit & vegetables",
        "icon": "bi-leaf",
        "theme": "produce",
    },
    {
        "slug": "dairy_proteins",
        "title": "Dairy & proteins",
        "subtitle": "Fridge & meat drawer",
        "icon": "bi-egg-fried",
        "theme": "dairy",
    },
    {
        "slug": "pantry_staples",
        "title": "Pantry staples",
        "subtitle": "Oils, grains & dry goods",
        "icon": "bi-box-seam",
        "theme": "staples",
    },
]


def _assign_zone(name: str) -> str:
    n = name.lower()
    for kw in _PRODUCE_KW:
        if kw in n:
            return "produce"
    for kw in _DAIRY_MEAT_KW:
        if kw in n:
            return "dairy_proteins"
    for kw in _PANTRY_KW:
        if kw in n:
            return "pantry_staples"
    return "pantry_staples"


def _category_for(name: str, zone_slug: str) -> str:
    n = name.lower()
    if zone_slug == "produce":
        return PantryItem.Category.PRODUCE
    if zone_slug == "dairy_proteins":
        meat_fish = (
            "chicken",
            "beef",
            "pork",
            "fish",
            "meat",
            "bacon",
            "turkey",
            "lamb",
            "shrimp",
            "salmon",
            "tuna",
            "steak",
            "sausage",
            "ham",
            "cod",
            "duck",
            "prawn",
            "squid",
            "crab",
            "lobster",
            "anchovy",
            "sardine",
            "trout",
            "veal",
            "mussel",
            "oyster",
        )
        if any(m in n for m in meat_fish):
            return PantryItem.Category.PROTEINS
        return PantryItem.Category.DAIRY
    spice_like = (
        "oil",
        "salt",
        "pepper",
        "spice",
        "vinegar",
        "sauce",
        "seasoning",
        "cumin",
        "paprika",
        "curry",
        "oregano",
        "thyme",
        "nutmeg",
        "cinnamon",
        "clove",
        "cardamom",
        "cocoa",
        "coffee",
        "tea",
        "wine",
        "extract",
        "molasses",
        "honey",
        "syrup",
        "ketchup",
        "mustard",
        "mayo",
        "worcestershire",
        "tabasco",
        "salsa",
        "jam",
        "marmalade",
        "gelatin",
        "miso",
        "tahini",
        "sake",
        "sherry",
        "brandy",
        "rum",
        "vanilla",
        "garam",
        "masala",
        "chili",
    )
    if any(s in n for s in spice_like):
        return PantryItem.Category.SPICES
    return PantryItem.Category.PANTRY


def _fetch_themealdb() -> list[dict[str, Any]] | None:
    if not getattr(settings, "PANTRY_USE_INGREDIENT_API", True):
        return None
    try:
        req = Request(THEMEALDB_LIST_URL, headers={"User-Agent": "SousChefAI/1.0"})
        with urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
        data = json.loads(raw)
        meals = data.get("meals")
        if not meals:
            return None
        return meals
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, json.JSONDecodeError) as e:
        logger.warning("Pantry ingredient API fetch failed: %s", e)
        return None


def _build_from_api(meals: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[tuple[str, str, str]]] = {
        "produce": [],
        "dairy_proteins": [],
        "pantry_staples": [],
    }

    for row in meals:
        iid = str(row.get("idIngredient") or "").strip()
        name = (row.get("strIngredient") or "").strip()
        if not iid or not name:
            continue
        zone_slug = _assign_zone(name)
        key = f"tmdb_{iid}"
        cat = _category_for(name, zone_slug)
        buckets[zone_slug].append((key, name, cat))

    lookup: dict[str, tuple[str, str]] = {}
    zones_out = []
    for meta in _ZONE_META:
        slug = meta["slug"]
        items = sorted(buckets[slug], key=lambda x: x[1].lower())[:MAX_PER_ZONE]
        zones_out.append(
            {
                **meta,
                "keys": [x[0] for x in items],
            }
        )
        for key, name, cat in items:
            lookup[key] = (cat, name)

    return {"zones": zones_out, "lookup": lookup, "source": "themealdb"}


def _build_static() -> dict[str, Any]:
    lookup: dict[str, tuple[str, str]] = {}
    for key, (cat, name) in presets_mod._QUICK.items():
        lookup[key] = (cat, name)
    return {
        "zones": [dict(z) for z in presets_mod.QUICK_ZONES],
        "lookup": lookup,
        "source": "static",
    }


def get_catalog() -> dict[str, Any]:
    """Return {zones, lookup, source}. Cached 24h."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    meals = _fetch_themealdb()
    if meals:
        catalog = _build_from_api(meals)
        # Allow legacy static preset keys in POSTs alongside API ids.
        catalog["lookup"].update(_build_static()["lookup"])
    else:
        catalog = _build_static()

    cache.set(CACHE_KEY, catalog, CACHE_TTL)
    return catalog


def get_zones() -> list[dict[str, Any]]:
    return get_catalog()["zones"]


def get_zone_by_slug(slug: str) -> dict[str, Any] | None:
    for z in get_zones():
        if z["slug"] == slug:
            return z
    return None


def lookup_preset(preset_key: str) -> tuple[str, str] | None:
    """
    Resolve preset_key to (PantryItem.Category value, display name).
    """
    cat = get_catalog()["lookup"].get(preset_key)
    if cat:
        return cat
    return presets_mod.get_preset(preset_key)


def resolve_icon(preset_key: str, display_name: str = "") -> str:
    if preset_key in presets_mod.ICON_BY_KEY:
        return presets_mod.ICON_BY_KEY[preset_key]
    if preset_key.startswith("tmdb_") and display_name:
        pool = (
            "bi-basket2",
            "bi-egg",
            "bi-leaf",
            "bi-droplet",
            "bi-sun",
            "bi-cloud",
            "bi-heart",
            "bi-star",
            "bi-circle",
        )
        return pool[abs(hash(display_name)) % len(pool)]
    return "bi-basket2"


def themealdb_ingredient_slug(display_name: str) -> str:
    """
    TheMealDB image paths use lowercase names with underscores for spaces.
    See https://www.themealdb.com/api.php — Ingredient Thumbnail Images.
    """
    s = (display_name or "").strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s or "ingredient"


def themealdb_ingredient_image_url(
    display_name: str, size: str = "small"
) -> str:
    """
    Public PNG thumbnails from TheMealDB CDN (no separate API key).
    Sizes: small | medium | large | full (full = no size suffix, .png only).
    """
    slug = themealdb_ingredient_slug(display_name)
    base = "https://www.themealdb.com/images/ingredients"
    if size == "medium":
        return f"{base}/{slug}-medium.png"
    if size == "large":
        return f"{base}/{slug}-large.png"
    if size == "full":
        return f"{base}/{slug}.png"
    return f"{base}/{slug}-small.png"


def ingredient_image_url(display_name: str, size: str = "small") -> str:
    """Return ingredient image URL, or empty string when images are disabled."""
    if not getattr(settings, "PANTRY_SHOW_INGREDIENT_IMAGES", True):
        return ""
    if not (display_name or "").strip():
        return ""
    return themealdb_ingredient_image_url(display_name, size=size)


def clear_catalog_cache() -> None:
    cache.delete(CACHE_KEY)
