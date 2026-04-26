"""
Ingredient catalogs: fetch from TheMealDB public API, classify into zones, cache.

Docs: https://www.themealdb.com/api.php
Fallback: local presets in pantry.presets when the API is unreachable.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

from .models import PantryItem
from . import presets as presets_mod

logger = logging.getLogger(__name__)

CACHE_KEY = "pantry.ingredient_catalog.v11"
CACHE_TTL = 60 * 60 * 24  # 24 hours

THEMEALDB_LIST_URL = getattr(
    settings,
    "PANTRY_INGREDIENT_LIST_URL",
    "https://www.themealdb.com/api/json/v1/1/list.php?i=list",
)
MAX_PER_ZONE = getattr(settings, "PANTRY_MAX_INGREDIENTS_PER_ZONE", 1500)

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

# Keep pantry staples focused on essential long-lasting items only.
_PANTRY_STAPLES_ALLOWED_KW = (
    # Grains / dry carb staples
    "rice",
    "pasta",
    "noodle",
    "flour",
    "cornmeal",
    "cornflour",
    "cornstarch",
    "starch",
    "semolina",
    "quinoa",
    "couscous",
    "bulgur",
    "barley",
    "oat",
    # Oils
    "oil",
    # Canned goods
    "bean",
    "lentil",
    "chickpea",
    "tomato",
    # Spices / seasonings
    "salt",
    "pepper",
    "spice",
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
    "chili",
    "garam",
    "masala",
    # Baking essentials
    "sugar",
    "yeast",
    "baking",
    "vanilla",
    "cocoa",
    # Condiments
    "vinegar",
    "sauce",
    "ketchup",
    "mustard",
    "mayo",
    "worcestershire",
    "tabasco",
    "salsa",
    "miso",
    "tahini",
    "soy",
)

# Priority routing to resolve keyword overlaps across zones.
# Example: "apple cider vinegar" must route to pantry staples, not produce.
_PRIORITY_ZONE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "pantry_staples",
        (
            "vinegar",
            "oil",
            "sauce",
            "stock",
            "flour",
            "sugar",
            "salt",
            "pepper",
            "paprika",
            "cumin",
            "oregano",
            "thyme",
            "nutmeg",
            "cinnamon",
            "clove",
            "cardamom",
            "chili powder",
            "curry",
            "rice",
            "pasta",
            "noodle",
            "bean",
            "lentil",
            "yeast",
            "cornstarch",
            "cornflour",
        ),
    ),
    (
        "dairy_proteins",
        (
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
        ),
    ),
)

_ZONE_META = [
    {
        "slug": "produce",
        "title": "Produce",
        "subtitle": "",
        "hero_description": (
            "Fresh vegetables, fruit, and herbs you’d find in the produce aisle or growing on your windowsill. "
            "Add what you usually keep on hand so your pantry reflects the colorful, seasonal side of your cooking—and "
            "recipes can suggest ingredients you’re more likely to have."
        ),
        "icon": "bi-leaf",
        "theme": "produce",
    },
    {
        "slug": "dairy_proteins",
        "title": "Dairy & Proteins",
        "subtitle": "Fridge & meat drawer",
        "hero_description": (
            "Eggs, dairy, and the proteins you store in the fridge or freezer. "
            "Log the cheeses, milks, yogurts, and meats you buy most often so your list stays grounded in what’s actually "
            "chilling at home—not a generic shopping template."
        ),
        "icon": "bi-egg-fried",
        "theme": "dairy",
    },
    {
        "slug": "pantry_staples",
        "title": "Pantry Staples",
        "subtitle": "Oils, grains & dry goods",
        "hero_description": (
            "Oils, grains, pasta, flour, spices, and the jars and boxes that live in your cupboards. "
            "These are the quiet workhorses behind most meals—capturing them here keeps your inventory honest when you "
            "plan from the shelf, not from memory."
        ),
        "icon": "bi-box-seam",
        "theme": "staples",
    },
]


_TYPE_TO_ZONE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "produce",
        (
            "vegetable",
            "vegetables",
            "fruit",
            "fruits",
            "herb",
            "herbs",
        ),
    ),
    (
        "dairy_proteins",
        (
            "meat",
            "poultry",
            "seafood",
            "fish",
            "dairy",
            "cheese",
            "egg",
            "eggs",
            "protein",
            "proteins",
        ),
    ),
    (
        "pantry_staples",
        (
            "spice",
            "spices",
            "seasoning",
            "seasonings",
            "sauce",
            "sauces",
            "condiment",
            "condiments",
            "grain",
            "grains",
            "pasta",
            "noodle",
            "noodles",
            "rice",
            "flour",
            "sweetener",
            "sweeteners",
            "oil",
            "oils",
            "vinegar",
            "vinegars",
            "bean",
            "beans",
            "lentil",
            "lentils",
            "nut",
            "nuts",
            "seed",
            "seeds",
        ),
    ),
)


def _assign_zone(name: str, ingredient_type: str = "") -> str:
    # main idea: this decides which catalog section an ingredient belongs to.
    # priority rules run first so mixed names are put in the most useful section for the user.
    n = name.lower()
    t = (ingredient_type or "").strip().lower()
    for zone_slug, keywords in _PRIORITY_ZONE_RULES:
        if any(kw in n for kw in keywords):
            return zone_slug
    if t:
        for zone_slug, keywords in _TYPE_TO_ZONE_RULES:
            if any(kw in t for kw in keywords):
                return zone_slug
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


def _is_allowed_pantry_staple(name: str, ingredient_type: str = "") -> bool:
    """True when ingredient matches the curated pantry staples definition."""
    n = (name or "").strip().lower()
    t = (ingredient_type or "").strip().lower()
    return any(kw in n or kw in t for kw in _PANTRY_STAPLES_ALLOWED_KW)


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


def _normalize_dedupe_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _canonical_ingredient_name(name: str) -> str:
    """
    Collapse verbose source labels to ingredient-like names.
    Example: "Beef (Babyfood, dinner, ...)" -> "Beef"
    """
    raw = (name or "").strip()
    if not raw:
        return ""
    # Remove parenthetical details and keep the first comma-separated head.
    s = re.sub(r"\([^)]*\)", "", raw).strip()
    if "," in s:
        s = s.split(",", 1)[0].strip()
    # Ingredient descriptions can include prep/composite phrases; keep base ingredient head.
    # Examples:
    # - "Beef and broccoli" -> "Beef"
    # - "Chicken with gravy" -> "Chicken"
    # - "Pork in sauce" -> "Pork"
    s = re.split(r"\b(and|with|in|on|from)\b", s, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    # Remove common trailing qualifiers.
    s = re.sub(r"\bas ingredient in recipes\b", "", s, flags=re.IGNORECASE).strip(" -_/")
    # Keep only the leading alpha/space segment so labels don't carry source noise.
    s = re.sub(r"[^A-Za-z\s-].*$", "", s).strip()
    s = re.sub(r"\s+", " ", s).strip()
    if s:
        kw = _extract_primary_keyword(s)
        if kw:
            return kw
    kw = _extract_primary_keyword(raw)
    return kw or s or raw


def _extract_primary_keyword(text: str) -> str:
    """
    Pick the first ingredient-like keyword from noisy descriptions.
    Example: "Almond butter sandwich (Survey...)" -> "Almond"
    """
    s = unicodedata.normalize("NFKD", (text or "").lower()).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return ""

    # Build phrase list from existing routing keywords so extraction stays consistent.
    phrases = set(_PRODUCE_KW) | set(_DAIRY_MEAT_KW) | set(_PANTRY_KW)
    # Prefer longer phrases when they start at same position.
    ordered = sorted(phrases, key=lambda p: (-len(p), p))

    best_phrase = ""
    best_pos = None
    for phrase in ordered:
        pattern = rf"\b{re.escape(phrase)}\b"
        m = re.search(pattern, s)
        if not m:
            continue
        pos = m.start()
        if best_pos is None or pos < best_pos:
            best_pos = pos
            best_phrase = phrase
        elif pos == best_pos and len(phrase) > len(best_phrase):
            best_phrase = phrase

    if best_phrase:
        return " ".join(w.capitalize() for w in best_phrase.split())
    return ""


def _format_name_with_type(name: str, ingredient_type: str = "") -> str:
    base = (name or "").strip()
    t = (ingredient_type or "").strip()
    if not base:
        return ""
    if not t:
        return base
    # Avoid double suffixes if a source already embeds it.
    if base.lower().endswith(f"({t.lower()})"):
        return base
    # If the base already includes a parenthetical tail, keep it as-is.
    if re.search(r"\([^)]*\)\s*$", base):
        return base
    return f"{base} ({t})"


def _build_from_api(meals: list[dict[str, Any]] | None) -> dict[str, Any]:
    # main idea: this converts themealdb ingredients into the structure used by the ui.
    # it creates zone lists for rendering and a lookup table for saving ingredients by key.
    buckets: dict[str, list[tuple[str, str, str]]] = {
        "produce": [],
        "dairy_proteins": [],
        "pantry_staples": [],
    }
    seen_names: set[str] = set()

    for row in meals or []:
        iid = str(row.get("idIngredient") or "").strip()
        name = (row.get("strIngredient") or "").strip()
        if not iid or not name:
            continue
        dedupe_name = _normalize_dedupe_name(name)
        if not dedupe_name or dedupe_name in seen_names:
            continue
        seen_names.add(dedupe_name)
        ingredient_type = str(row.get("strType") or "")
        zone_slug = _assign_zone(name, ingredient_type)
        if zone_slug == "pantry_staples" and not _is_allowed_pantry_staple(name, ingredient_type):
            continue
        key = f"tmdb_{iid}"
        cat = _category_for(name, zone_slug)
        display_name = _format_name_with_type(name, ingredient_type)
        buckets[zone_slug].append((key, display_name, cat))

    lookup: dict[str, tuple[str, str]] = {}
    zones_out = []
    for meta in _ZONE_META:
        slug = meta["slug"]
        items = sorted(buckets[slug], key=lambda x: x[1].lower())
        if MAX_PER_ZONE and MAX_PER_ZONE > 0:
            items = items[:MAX_PER_ZONE]
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
    # main idea: this is the pantry catalog entry point.
    # it tries cached api data first, then falls back to local presets if the api is unavailable.
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
    # used by the url, for example /pantry/produce/.
    # it finds the matching catalog zone that the template will render.
    for z in get_zones():
        if z["slug"] == slug:
            return z
    return None


def lookup_preset(preset_key: str) -> tuple[str, str] | None:
    # this connects a hidden form value back to a real pantry category and name.
    # without this lookup, the add button would only send a key and not a usable ingredient.
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
    # TheMealDB filenames are ASCII-ish (e.g. "Crème..." -> "creme...").
    # Normalize accents/diacritics so we generate a more reliable slug.
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    # TheMealDB docs: thumbnail URLs match ingredient name with underscores for spaces.
    # That implies we should preserve punctuation such as '-' and ','.
    s = re.sub(r"\s+", "_", s)
    # Avoid breaking the URL path component.
    s = s.replace("/", "_").replace("\\", "_")
    # Collapse repeated underscores (e.g. accidental double spaces).
    s = re.sub(r"_+", "_", s)
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
    # Keep ingredient-specific variants (e.g. "Beef Brisket"), remove only a trailing
    # source/type suffix like "(Meat)" so we don't collapse everything to "Beef".
    image_base_name = re.sub(r"\s*\([^)]*\)\s*$", "", display_name).strip()
    if not image_base_name:
        image_base_name = (display_name or "").strip()
    return themealdb_ingredient_image_url(image_base_name, size=size)


def clear_catalog_cache() -> None:
    cache.delete(CACHE_KEY)
