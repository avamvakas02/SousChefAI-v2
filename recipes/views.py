import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from .daily_suggestions import get_daily_suggested_recipes
from .discovery_service import discover_pantry_recipes
from .meal_planner_service import enrich_recipes_with_scores
from subscriptions.models import CustomerSubscription
from subscriptions.permissions import require_plan
from subscriptions.quota import consume_recipe_generation, effective_plan, usage_remaining


@login_required
def recipe_discovery_page(request):
    plan = effective_plan(request.user)
    remaining = usage_remaining(request)
    return render(
        request,
        "recipes/recipe_discovery.html",
        {
            "daily_suggested_recipes": get_daily_suggested_recipes(),
            "current_plan": plan,
            "usage_remaining": remaining,
            "usage_unlimited": remaining is None,
        },
    )


@login_required
def recipe_detail_page(request):
    return render(request, "recipes/recipe_detail.html")


@login_required
@require_POST
def discover_recipes_api(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"errors": ["Invalid JSON body."]}, status=400)

    try:
        if not consume_recipe_generation(request):
            remaining = usage_remaining(request)
            return JsonResponse(
                {
                    "errors": [
                        "You have reached your monthly recipe generation limit for your current plan."
                    ],
                    "fallback_message": "Upgrade your plan to continue generating recipes.",
                    "meta": {
                        "current_plan": effective_plan(request.user),
                        "usage_remaining": 0 if remaining is None else remaining,
                        "upgrade_url": "/pricing/",
                    },
                    "recipes": [],
                },
                status=402,
            )
        result = discover_pantry_recipes(user=request.user, payload=payload)
        result["recipes"] = enrich_recipes_with_scores(result.get("recipes") or [])
        result.setdefault("meta", {})
        result["meta"]["current_plan"] = effective_plan(request.user)
        remaining_after = usage_remaining(request)
        result["meta"]["usage_remaining"] = (
            None if remaining_after is None else max(remaining_after, 0)
        )
        return JsonResponse(result, status=200)
    except ValueError as exc:
        return JsonResponse({"errors": [str(exc)]}, status=400)
    except Exception:
        return JsonResponse(
            {
                "meta": {
                    "used_pantry_count": 0,
                    "requested_count": 5,
                    "returned_count": 0,
                    "pantry_only": bool(payload.get("pantry_only", False)),
                    "max_missing": int(payload.get("max_missing", 2)),
                },
                "recipes": [],
                "fallback_message": "Unable to generate recipes right now. Please try again.",
                "errors": ["Discovery service failure."],
            },
            status=500,
        )

@login_required
@require_POST
def ask_souschef_api(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)
    
    question = payload.get("question")
    if not question:
        return JsonResponse({"error": "Question is required."}, status=400)
        
    recipe_title = payload.get("recipe_title", "")
    ingredients = payload.get("ingredients", [])
    step_text = payload.get("step_text", "")
    chat_history = payload.get("history", [])

    from .chat_service import ask_souschef_chatbot
    try:
        answer = ask_souschef_chatbot(recipe_title, ingredients, step_text, question, chat_history)
        return JsonResponse({"answer": answer}, status=200)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@login_required
@require_POST
@require_plan(CustomerSubscription.Plan.REGULAR, api=True)
def toggle_favorite(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    recipe_id = payload.get("recipe_id")
    action = payload.get("action")  # 'add' or 'remove'
    recipe_data = payload.get("recipe_data")

    if not recipe_id or not action:
        return JsonResponse({"error": "Missing recipe_id or action."}, status=400)

    from .models import FavoriteRecipe

    if action == "add":
        if not recipe_data:
            return JsonResponse({"error": "Missing recipe_data for adding favorite."}, status=400)
        
        FavoriteRecipe.objects.get_or_create(
            user=request.user,
            recipe_id=recipe_id,
            defaults={
                "title": recipe_data.get("title", "Untitled Recipe"),
                "image_url": recipe_data.get("image_url") or recipe_data.get("image") or "",
                "recipe_data": recipe_data,
            }
        )
        return JsonResponse({"status": "added"}, status=200)
    
    elif action == "remove":
        FavoriteRecipe.objects.filter(user=request.user, recipe_id=recipe_id).delete()
        return JsonResponse({"status": "removed"}, status=200)
    
    return JsonResponse({"error": "Invalid action."}, status=400)

@login_required
@require_plan(CustomerSubscription.Plan.REGULAR, api=True)
def check_favorite_status(request):
    recipe_id = request.GET.get("recipe_id")
    if not recipe_id:
        return JsonResponse({"error": "Missing recipe_id."}, status=400)
    
    from .models import FavoriteRecipe
    is_favorite = FavoriteRecipe.objects.filter(user=request.user, recipe_id=recipe_id).exists()
    return JsonResponse({"is_favorite": is_favorite}, status=200)


