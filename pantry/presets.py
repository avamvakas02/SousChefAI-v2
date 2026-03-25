"""
Whitelisted quick-add ingredients (tap only). Keys are posted as preset_key.
"""

from .models import PantryItem

_QUICK = {
    # Produce
    "tomatoes": (PantryItem.Category.PRODUCE, "Tomatoes"),
    "onions": (PantryItem.Category.PRODUCE, "Onions"),
    "garlic": (PantryItem.Category.PRODUCE, "Garlic"),
    "potatoes": (PantryItem.Category.PRODUCE, "Potatoes"),
    "carrots": (PantryItem.Category.PRODUCE, "Carrots"),
    "lettuce": (PantryItem.Category.PRODUCE, "Lettuce"),
    "bell_peppers": (PantryItem.Category.PRODUCE, "Bell peppers"),
    "lemons": (PantryItem.Category.PRODUCE, "Lemons"),
    "mushrooms": (PantryItem.Category.PRODUCE, "Mushrooms"),
    "spinach": (PantryItem.Category.PRODUCE, "Spinach"),
    # Dairy & proteins
    "milk": (PantryItem.Category.DAIRY, "Milk"),
    "eggs": (PantryItem.Category.DAIRY, "Eggs"),
    "butter": (PantryItem.Category.DAIRY, "Butter"),
    "yogurt": (PantryItem.Category.DAIRY, "Greek yogurt"),
    "cheddar": (PantryItem.Category.DAIRY, "Cheddar"),
    "chicken_breast": (PantryItem.Category.PROTEINS, "Chicken breast"),
    "ground_beef": (PantryItem.Category.PROTEINS, "Ground beef"),
    "bacon": (PantryItem.Category.PROTEINS, "Bacon"),
    "tofu": (PantryItem.Category.PROTEINS, "Tofu"),
    # Pantry staples
    "olive_oil": (PantryItem.Category.SPICES, "Olive oil"),
    "rice": (PantryItem.Category.PANTRY, "Rice"),
    "pasta": (PantryItem.Category.PANTRY, "Pasta"),
    "flour": (PantryItem.Category.PANTRY, "Flour"),
    "sugar": (PantryItem.Category.PANTRY, "Sugar"),
    "salt": (PantryItem.Category.SPICES, "Salt"),
    "black_pepper": (PantryItem.Category.SPICES, "Black pepper"),
    "canned_tomatoes": (PantryItem.Category.PANTRY, "Canned tomatoes"),
    "stock": (PantryItem.Category.PANTRY, "Chicken stock"),
    "beans": (PantryItem.Category.PANTRY, "Beans"),
}

# Bootstrap Icons per ingredient (1.11-safe, decorative)
ICON_BY_KEY = {
    "tomatoes": "bi-heart-fill",
    "onions": "bi-layers-fill",
    "garlic": "bi-flower2",
    "potatoes": "bi-circle-fill",
    "carrots": "bi-caret-up-fill",
    "lettuce": "bi-leaf",
    "bell_peppers": "bi-brightness-high-fill",
    "lemons": "bi-sun-fill",
    "mushrooms": "bi-cloud-fill",
    "spinach": "bi-droplet-fill",
    "milk": "bi-cup-straw",
    "eggs": "bi-egg",
    "butter": "bi-square-fill",
    "yogurt": "bi-cup-fill",
    "cheddar": "bi-grid-3x3-gap-fill",
    "chicken_breast": "bi-heart-pulse",
    "ground_beef": "bi-record-circle",
    "bacon": "bi-wind",
    "tofu": "bi-box-fill",
    "olive_oil": "bi-droplet-fill",
    "rice": "bi-water",
    "pasta": "bi-link-45deg",
    "flour": "bi-cloud-snow",
    "sugar": "bi-star-fill",
    "salt": "bi-circle-fill",
    "black_pepper": "bi-circle-half",
    "canned_tomatoes": "bi-box-seam",
    "stock": "bi-cup-hot-fill",
    "beans": "bi-heart-fill",
}


def get_preset(preset_key: str):
    """Return (category, display_name) or None if unknown."""
    row = _QUICK.get(preset_key)
    if not row:
        return None
    return row[0], row[1]


def get_icon(preset_key: str) -> str:
    return ICON_BY_KEY.get(preset_key, "bi-basket2")


QUICK_ZONES = [
    {
        "slug": "produce",
        "title": "Produce",
        "subtitle": "Fresh fruit & vegetables",
        "icon": "bi-leaf",
        "theme": "produce",
        "keys": [
            "tomatoes",
            "onions",
            "garlic",
            "potatoes",
            "carrots",
            "lettuce",
            "bell_peppers",
            "lemons",
            "mushrooms",
            "spinach",
        ],
    },
    {
        "slug": "dairy_proteins",
        "title": "Dairy & proteins",
        "subtitle": "Fridge & meat drawer",
        "icon": "bi-egg-fried",
        "theme": "dairy",
        "keys": [
            "milk",
            "eggs",
            "butter",
            "yogurt",
            "cheddar",
            "chicken_breast",
            "ground_beef",
            "bacon",
            "tofu",
        ],
    },
    {
        "slug": "pantry_staples",
        "title": "Pantry staples",
        "subtitle": "Oils, grains & dry goods",
        "icon": "bi-box-seam",
        "theme": "staples",
        "keys": [
            "olive_oil",
            "rice",
            "pasta",
            "flour",
            "sugar",
            "salt",
            "black_pepper",
            "canned_tomatoes",
            "stock",
            "beans",
        ],
    },
]


def get_zone_by_slug(slug: str):
    for z in QUICK_ZONES:
        if z["slug"] == slug:
            return z
    return None
