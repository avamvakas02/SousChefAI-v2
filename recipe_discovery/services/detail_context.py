from pantry.models import PantryItem
from subscriptions.models import CustomerSubscription
from subscriptions.permissions import has_required_plan

from recipe_discovery.recipe_ingredients import filter_household_staples
from recipe_discovery.services.gemini_recipes import (
    _build_recipe_description,
    _ensure_minimum_steps,
)


def _recipe_detail_context_for_user(recipe: dict, user) -> dict:
    # main idea: this builds the detail page context from the recipe and the user pantry.
    # needed ingredients are split into already have and still missing.
    pantry_names = list(PantryItem.objects.filter(user=user).values_list("name", flat=True))
    pantry_lookup = {
        (name or "").strip().lower() for name in pantry_names if (name or "").strip()
    }
    needed = [
        str(item).strip() for item in (recipe.get("needed") or []) if str(item).strip()
    ]
    needed = filter_household_staples(needed)
    pantry_have = [item for item in needed if item.lower() in pantry_lookup]
    pantry_missing = [item for item in needed if item.lower() not in pantry_lookup]

    recipe_context = dict(recipe)
    recipe_context["steps"] = _ensure_minimum_steps(recipe.get("steps") or [], minimum=12)
    recipe_context["description"] = _build_recipe_description(recipe)
    return {
        "recipe": recipe_context,
        "pantry_have": pantry_have,
        "pantry_missing": pantry_missing,
        "can_save_recipe": has_required_plan(user, CustomerSubscription.Plan.PREMIUM),
    }


