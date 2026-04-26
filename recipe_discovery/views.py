from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from pantry.models import PantryItem
from subscriptions.models import CustomerSubscription
from subscriptions.permissions import require_plan
from subscriptions.quota import consume_recipe_generation, usage_remaining
from users.models import UserProfile

from .models import SavedRecipe
from .recipe_ingredients import filter_household_staples
from .services.detail_context import _recipe_detail_context_for_user
from .services.gemini_recipes import (
    _build_recipe_description,
    _ensure_minimum_steps,
    _gemini_generate_recipe_cards,
)
from .services.recommendations import (
    _daily_recommended_recipes_for_user,
    _next_daily_recommendation_refresh_iso,
    _recommended_recipe_by_id,
)


@login_required
def recipe_discovery(request):
    # main idea: pantry ingredients are read from the database and sent to the recipe generator.
    # generated cards stay in the session so the detail page can open them later.
    pantry_names = list(
        PantryItem.objects.filter(user=request.user).values_list("name", flat=True)
    )
    recipes = request.session.get("recipe_discovery_cards", [])
    last_goal = request.session.get("recipe_discovery_goal", "")
    regenerate_count = int(request.session.get("recipe_discovery_regenerate_count", 0) or 0)
    remaining_generations = usage_remaining(request)
    recommended_recipes = _daily_recommended_recipes_for_user(request.user, pantry_names)

    if request.method == "POST":
        action = (request.POST.get("action") or "generate").strip()
        is_regenerate = action == "regenerate"
        user_goal = (request.POST.get("goal") or "").strip()
        if is_regenerate:
            user_goal = last_goal
        else:
            request.session["recipe_discovery_goal"] = user_goal
            request.session["recipe_discovery_regenerate_count"] = 0
            regenerate_count = 0
        last_goal = user_goal

        if not pantry_names:
            messages.warning(request, "Add pantry ingredients before generating recipes.")
        elif is_regenerate and not recipes:
            messages.warning(request, "Generate recipes before regenerating them.")
        elif is_regenerate and regenerate_count >= 2:
            messages.warning(
                request,
                "You have used both recipe regenerations for this set. Start a new generation to reset them.",
            )
        elif not consume_recipe_generation(request):
            messages.warning(
                request,
                "You have reached your monthly recipe generation limit. Upgrade to continue.",
            )
        else:
            try:
                skill_level = request.user.profile.skill_level
            except UserProfile.DoesNotExist:
                skill_level = UserProfile.SkillLevel.BEGINNER
            generation_goal = user_goal
            if is_regenerate:
                previous_titles = [
                    str(recipe.get("title") or "").strip()
                    for recipe in recipes
                    if str(recipe.get("title") or "").strip()
                ]
                avoid_line = ""
                if previous_titles:
                    avoid_line = (
                        " Avoid repeating these recipe titles or concepts: "
                        f"{', '.join(previous_titles[:4])}."
                    )
                generation_goal = (
                    f"{user_goal} Fresh alternate set.{avoid_line}"
                ).strip()
            # this is the main ai call.
            # pantry names, user goal, and skill level become the prompt inputs.
            recipes, ai_error = _gemini_generate_recipe_cards(
                pantry_names, generation_goal, skill_level
            )
            recipes = recipes[:4]
            request.session["recipe_discovery_cards"] = recipes
            if recipes:
                if is_regenerate:
                    regenerate_count += 1
                    request.session["recipe_discovery_regenerate_count"] = regenerate_count
                    messages.success(request, "AI recipes regenerated from your pantry.")
                else:
                    messages.success(request, "AI recipes generated from your pantry.")
            else:
                messages.error(
                    request,
                    f"AI recipe generation failed. {ai_error or 'Check your Gemini API key/model and try again.'}",
                )
            remaining_generations = usage_remaining(request)

    return render(
        request,
        "recipe_discovery/recipe-discovery.html",
        {
            "pantry_count": len(pantry_names),
            "recipes": recipes,
            "last_goal": last_goal,
            "recommended_recipes": recommended_recipes,
            "recommendations_refresh_at": _next_daily_recommendation_refresh_iso(),
            "remaining_generations": remaining_generations,
            "regenerate_count": regenerate_count,
            "regenerations_left": max(0, 2 - regenerate_count),
        },
    )


@login_required
def recipe_discovery_detail(request, recipe_id):
    # main idea: the detail page tries session recipes first, then daily recommendations, then saved recipes.
    # after finding the recipe, it compares needed ingredients with the user pantry.
    pantry_names = list(
        PantryItem.objects.filter(user=request.user).values_list("name", flat=True)
    )
    recipes = request.session.get("recipe_discovery_cards", [])
    recipe = next((r for r in recipes if r.get("id") == recipe_id), None)
    if not recipe:
        recipe = _recommended_recipe_by_id(recipe_id, pantry_names)
    if not recipe:
        saved = (
            SavedRecipe.objects.filter(user=request.user, recipe_id=recipe_id)
            .values(
                "recipe_id",
                "title",
                "description",
                "image_url",
                "time_minutes",
                "difficulty",
                "portions",
                "pantry_match",
                "needed",
                "steps",
            )
            .first()
        )
        if saved:
            recipe = {
                "id": saved["recipe_id"],
                "title": saved["title"],
                "description": saved["description"],
                "image_url": saved["image_url"],
                "time_minutes": saved["time_minutes"],
                "difficulty": saved["difficulty"],
                "portions": saved["portions"],
                "pantry_match": saved["pantry_match"],
                "needed": saved["needed"] or [],
                "steps": saved["steps"] or [],
            }
    if not recipe:
        messages.warning(request, "Generate recipes first to view details.")
        return render(
            request,
            "recipe_discovery/recipe-discovery-detail.html",
            {"recipe": None},
        )
    context = _recipe_detail_context_for_user(recipe, request.user)
    return render(request, "recipe_discovery/recipe-discovery-detail.html", context)


@login_required
@require_plan(CustomerSubscription.Plan.PREMIUM)
def save_recipe(request, recipe_id):
    # main idea: premium users can store a recipe permanently in the database.
    # household staples are removed before saving so the shopping list stays useful.
    if request.method != "POST":
        return redirect("recipe_discovery_detail", recipe_id=recipe_id)

    pantry_names = list(
        PantryItem.objects.filter(user=request.user).values_list("name", flat=True)
    )
    recipes = request.session.get("recipe_discovery_cards", [])
    recipe = next((r for r in recipes if r.get("id") == recipe_id), None)
    if not recipe:
        recipe = _recommended_recipe_by_id(recipe_id, pantry_names)
    if not recipe:
        messages.warning(request, "Recipe not found. Generate recipes first.")
        return redirect("recipe_discovery")

    defaults = {
        "title": str(recipe.get("title") or "").strip()[:255] or "Untitled recipe",
        "description": _build_recipe_description(recipe),
        "image_url": str(recipe.get("image_url") or "").strip(),
        "time_minutes": int(recipe.get("time_minutes") or 30),
        "difficulty": str(recipe.get("difficulty") or "Medium")[:32],
        "portions": int(recipe.get("portions") or 2),
        "pantry_match": int(recipe.get("pantry_match") or 0),
        "needed": filter_household_staples(
            [str(item).strip() for item in (recipe.get("needed") or []) if str(item).strip()]
        ),
        "steps": _ensure_minimum_steps(recipe.get("steps") or [], minimum=12),
    }
    _, created = SavedRecipe.objects.update_or_create(
        user=request.user,
        recipe_id=recipe_id,
        defaults=defaults,
    )
    if created:
        messages.success(request, "Recipe saved successfully.")
    else:
        messages.success(request, "Recipe updated in your saved recipes.")
    return redirect("saved_recipes")


@login_required
@require_plan(CustomerSubscription.Plan.PREMIUM)
def saved_recipes(request):
    # main idea: this page renders only the recipes saved by the logged in user.
    recipes = SavedRecipe.objects.filter(user=request.user)
    return render(
        request,
        "recipe_discovery/saved-recipes.html",
        {"saved_recipes": recipes},
    )
