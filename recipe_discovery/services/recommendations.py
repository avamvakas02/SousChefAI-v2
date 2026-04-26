from datetime import datetime, time, timedelta
from random import Random

from django.templatetags.static import static
from django.utils import timezone

from recipe_discovery.recipe_ingredients import filter_household_staples


RECOMMENDED_RECIPE_POOL = [
    {
        "id": "daily-tomato-basil-linguine",
        "title": "Tomato Basil Linguine",
        "description": "A bright pantry pasta with crushed tomatoes, garlic, basil, and a glossy olive-oil finish.",
        "time_minutes": 25,
        "difficulty": "Easy",
        "portions": 2,
        "needed": ["linguine", "tomatoes", "garlic", "basil", "parmesan", "olive oil"],
        "steps": [
            "Bring a large pot of salted water to a boil.",
            "Cook the linguine until just shy of al dente.",
            "Warm olive oil in a skillet over medium heat.",
            "Add sliced garlic and cook until fragrant but not browned.",
            "Stir in crushed tomatoes and simmer until slightly thickened.",
            "Transfer the pasta into the sauce with a splash of pasta water.",
            "Toss until the sauce coats the linguine evenly.",
            "Fold in torn basil and grated parmesan.",
            "Taste and adjust seasoning before serving.",
        ],
    },
    {
        "id": "daily-lemon-garlic-salmon",
        "title": "Lemon Garlic Salmon",
        "description": "Crisp-edged salmon with lemon, garlic, and a quick pan sauce for a fast weeknight plate.",
        "time_minutes": 22,
        "difficulty": "Medium",
        "portions": 2,
        "needed": ["salmon", "lemon", "garlic", "butter", "parsley", "olive oil"],
        "steps": [
            "Pat the salmon dry and season both sides.",
            "Heat olive oil in a nonstick skillet over medium-high heat.",
            "Place the salmon skin-side down and press gently for even contact.",
            "Cook until the skin is crisp and the fish is mostly opaque.",
            "Flip the fillets and lower the heat.",
            "Add butter, minced garlic, and lemon juice to the pan.",
            "Spoon the sauce over the salmon until just cooked through.",
            "Finish with parsley and extra lemon zest.",
        ],
    },
    {
        "id": "daily-chicken-tomato-skillet",
        "title": "Chicken Tomato Skillet",
        "description": "Juicy chicken simmered with tomatoes, herbs, and garlic in one easy skillet.",
        "time_minutes": 35,
        "difficulty": "Easy",
        "portions": 3,
        "needed": ["chicken", "tomatoes", "onion", "garlic", "oregano", "rice"],
        "steps": [
            "Season the chicken pieces on all sides.",
            "Sear the chicken in a hot skillet until golden.",
            "Remove the chicken and soften onion in the same pan.",
            "Add garlic and oregano and cook until aromatic.",
            "Pour in tomatoes and scrape up the browned bits.",
            "Return the chicken to the skillet.",
            "Simmer until the chicken is cooked through and tender.",
            "Serve over warm rice with spoonfuls of sauce.",
        ],
    },
    {
        "id": "daily-creamy-tomato-soup",
        "title": "Creamy Tomato Basil Soup",
        "description": "A comforting tomato soup with basil, a silky finish, and crisp toast on the side.",
        "time_minutes": 30,
        "difficulty": "Easy",
        "portions": 4,
        "needed": ["tomatoes", "onion", "garlic", "basil", "cream", "bread"],
        "steps": [
            "Soften onion in olive oil over medium heat.",
            "Add garlic and cook briefly until fragrant.",
            "Stir in tomatoes and simmer until deeply flavored.",
            "Blend the soup until smooth.",
            "Return it to the pot and stir in cream.",
            "Add basil and simmer gently for a few minutes.",
            "Toast bread until crisp and golden.",
            "Serve the soup hot with toast on the side.",
        ],
    },
    {
        "id": "daily-garlic-herb-omelette",
        "title": "Garlic Herb Omelette",
        "description": "A quick fluffy omelette filled with herbs, garlic, and a little cheese.",
        "time_minutes": 15,
        "difficulty": "Easy",
        "portions": 1,
        "needed": ["eggs", "garlic", "parsley", "cheese", "butter"],
        "steps": [
            "Beat the eggs until no streaks remain.",
            "Melt butter in a small nonstick skillet.",
            "Cook minced garlic for a few seconds until fragrant.",
            "Pour in the eggs and stir gently as they set.",
            "Sprinkle herbs and cheese over one side.",
            "Fold the omelette and cook until just set.",
            "Slide onto a plate and serve immediately.",
        ],
    },
    {
        "id": "daily-balsamic-chicken-salad",
        "title": "Balsamic Chicken Salad",
        "description": "A fresh chicken salad with tomatoes, greens, and a tangy balsamic dressing.",
        "time_minutes": 28,
        "difficulty": "Easy",
        "portions": 2,
        "needed": ["chicken", "lettuce", "tomatoes", "balsamic vinegar", "olive oil", "mozzarella"],
        "steps": [
            "Season and sear the chicken until browned.",
            "Lower the heat and cook until the center is done.",
            "Rest the chicken before slicing.",
            "Whisk balsamic vinegar with olive oil for the dressing.",
            "Arrange lettuce and tomatoes in a large bowl.",
            "Add sliced chicken and torn mozzarella.",
            "Drizzle with dressing and toss lightly.",
        ],
    },
    {
        "id": "daily-spicy-tuna-rice-bowl",
        "title": "Spicy Tuna Rice Bowl",
        "description": "A fast rice bowl with tuna, crunchy vegetables, and a creamy chili sauce.",
        "time_minutes": 18,
        "difficulty": "Easy",
        "portions": 2,
        "needed": ["tuna", "rice", "cucumber", "carrot", "mayonnaise", "chili sauce"],
        "steps": [
            "Warm cooked rice and divide it between bowls.",
            "Flake tuna into a small bowl.",
            "Mix mayonnaise with chili sauce until smooth.",
            "Fold the spicy sauce into the tuna.",
            "Slice cucumber and shred carrot.",
            "Top the rice with tuna and vegetables.",
            "Finish with extra chili sauce if desired.",
        ],
    },
    {
        "id": "daily-herbed-potato-hash",
        "title": "Herbed Potato Hash",
        "description": "Crispy potatoes with onion, herbs, and a runny egg for a satisfying meal.",
        "time_minutes": 32,
        "difficulty": "Medium",
        "portions": 2,
        "needed": ["potatoes", "onion", "eggs", "parsley", "paprika", "olive oil"],
        "steps": [
            "Dice potatoes into small even pieces.",
            "Parboil the potatoes until barely tender.",
            "Drain and let them steam dry.",
            "Cook onion in olive oil until softened.",
            "Add potatoes and paprika to the skillet.",
            "Cook until the potatoes are crisp and browned.",
            "Make wells and crack eggs into the hash.",
            "Cover until the eggs are set to your liking.",
        ],
    },
    {
        "id": "daily-garlic-mushroom-toast",
        "title": "Garlic Mushroom Toast",
        "description": "Golden mushrooms on crisp toast with garlic, herbs, and a creamy finish.",
        "time_minutes": 20,
        "difficulty": "Easy",
        "portions": 2,
        "needed": ["mushrooms", "bread", "garlic", "thyme", "cream cheese", "butter"],
        "steps": [
            "Toast the bread until crisp.",
            "Slice mushrooms evenly.",
            "Melt butter in a skillet over medium-high heat.",
            "Cook mushrooms until browned and their moisture evaporates.",
            "Add garlic and thyme and cook briefly.",
            "Spread cream cheese over the toast.",
            "Pile mushrooms on top and serve warm.",
        ],
    },
    {
        "id": "daily-chickpea-vegetable-curry",
        "title": "Chickpea Vegetable Curry",
        "description": "A cozy chickpea curry with vegetables, tomato, and warm spices.",
        "time_minutes": 38,
        "difficulty": "Medium",
        "portions": 4,
        "needed": ["chickpeas", "tomatoes", "onion", "garlic", "curry powder", "spinach", "rice"],
        "steps": [
            "Cook onion in oil until soft and lightly golden.",
            "Add garlic and curry powder and stir for one minute.",
            "Pour in tomatoes and simmer until thickened.",
            "Add chickpeas and a splash of water.",
            "Simmer until the chickpeas absorb the sauce.",
            "Fold in spinach until wilted.",
            "Taste and adjust seasoning.",
            "Serve the curry over rice.",
        ],
    },
]

RECOMMENDED_RECIPE_IMAGES = {
    "daily-tomato-basil-linguine": "images/pantry-frustration.jpg",
    "daily-lemon-garlic-salmon": "images/pantry-frustration.jpg",
    "daily-chicken-tomato-skillet": "images/pantry-frustration.jpg",
    "daily-creamy-tomato-soup": "images/pantry-frustration.jpg",
    "daily-garlic-herb-omelette": "images/pantry-frustration.jpg",
    "daily-balsamic-chicken-salad": "images/pantry-frustration.jpg",
    "daily-spicy-tuna-rice-bowl": "images/pantry-frustration.jpg",
    "daily-herbed-potato-hash": "images/pantry-frustration.jpg",
    "daily-garlic-mushroom-toast": "images/pantry-frustration.jpg",
    "daily-chickpea-vegetable-curry": "images/pantry-frustration.jpg",
}


def _normalize_tokens(values: list[str]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        lowered = (value or "").strip().lower()
        if not lowered:
            continue
        for part in lowered.replace(",", " ").replace("-", " ").split():
            clean = part.strip(" .!?:;()[]{}\"'")
            if len(clean) >= 3:
                tokens.add(clean)
    return tokens


def _prepare_recommended_recipe(recipe: dict, pantry_names: list[str]) -> dict:
    # main idea: this prepares a static daily recipe so it behaves like an ai recipe card.
    # pantry_match is calculated by comparing recipe ingredients to pantry ingredient tokens.
    recommended = dict(recipe)
    needed = filter_household_staples(
        [str(item).strip() for item in (recommended.get("needed") or []) if str(item).strip()]
    )
    pantry_tokens = _normalize_tokens(pantry_names)
    ingredient_tokens = _normalize_tokens(needed)
    pantry_match = int(
        round(len(pantry_tokens.intersection(ingredient_tokens)) / max(len(ingredient_tokens), 1) * 100)
    )
    recommended["needed"] = needed
    recommended["steps"] = [
        str(step).strip() for step in (recommended.get("steps") or []) if str(step).strip()
    ]
    recommended["pantry_match"] = pantry_match
    recommended["fallback_image_url"] = static("images/hero-image.jpg")
    recommended["image_url"] = static(
        RECOMMENDED_RECIPE_IMAGES.get(
            str(recommended.get("id") or ""),
            "images/hero-image.jpg",
        )
    )
    return recommended


def _daily_recommended_recipes_for_user(user, pantry_names: list[str], limit: int = 6) -> list[dict]:
    # main idea: recommendations change daily but stay stable during the same day.
    # the seed uses the date and user id, so each user gets their own order.
    seed = f"{timezone.localdate().isoformat()}:{getattr(user, 'pk', 'anonymous')}"
    rng = Random(seed)
    recipes = list(RECOMMENDED_RECIPE_POOL)
    rng.shuffle(recipes)
    return [_prepare_recommended_recipe(recipe, pantry_names) for recipe in recipes[:limit]]


def _next_daily_recommendation_refresh_iso() -> str:
    next_day = timezone.localdate() + timedelta(days=1)
    next_midnight = datetime.combine(
        next_day,
        time.min,
        tzinfo=timezone.get_current_timezone(),
    )
    return next_midnight.isoformat()


def _recommended_recipe_by_id(recipe_id: str, pantry_names: list[str]) -> dict | None:
    recipe = next(
        (recipe for recipe in RECOMMENDED_RECIPE_POOL if recipe.get("id") == recipe_id),
        None,
    )
    if not recipe:
        return None
    return _prepare_recommended_recipe(recipe, pantry_names)


