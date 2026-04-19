import re
from typing import Any, Dict, List


_PRICE_HINTS_USD = {
    "salmon": 6.5,
    "beef": 5.2,
    "chicken": 3.4,
    "shrimp": 5.8,
    "rice": 0.9,
    "pasta": 1.0,
    "tomato": 0.8,
    "onion": 0.6,
    "garlic": 0.4,
    "egg": 0.5,
    "milk": 1.1,
    "cheese": 1.8,
    "butter": 1.2,
    "olive oil": 0.9,
    "lemon": 0.6,
    "bread": 1.4,
}


def enrich_recipes_with_scores(recipes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for recipe in recipes:
        if not isinstance(recipe, dict):
            continue
        working = dict(recipe)
        working["cost_estimate"] = estimate_recipe_cost(working)
        nutrition_score = estimate_nutrition_score(working.get("macros", {}))
        pantry_match = int(working.get("pantry_match_percent") or 0)
        per_serving = float(working["cost_estimate"]["per_serving_usd"])
        affordability = max(0.0, min(100.0, 100.0 - (per_serving * 18.0)))
        value_score = int(
            round((nutrition_score * 0.4) + (pantry_match * 0.35) + (affordability * 0.25))
        )
        working["nutrition_score"] = nutrition_score
        working["value_score"] = max(0, min(value_score, 100))
        enriched.append(working)
    return enriched


def estimate_recipe_cost(recipe: Dict[str, Any]) -> Dict[str, Any]:
    ingredients = recipe.get("ingredients") or []
    if not isinstance(ingredients, list):
        ingredients = []
    total = 0.0
    for item in ingredients:
        label = str(item or "").strip().lower()
        if not label:
            continue
        matched = False
        for key, price in _PRICE_HINTS_USD.items():
            if key in label:
                total += price
                matched = True
                break
        if not matched:
            total += 1.25

    servings = int(recipe.get("servings") or 2)
    servings = max(1, min(servings, 12))
    per_serving = total / servings
    return {
        "currency": "USD",
        "total_usd": round(total, 2),
        "per_serving_usd": round(per_serving, 2),
    }


def estimate_nutrition_score(macros: Dict[str, Any]) -> int:
    if not isinstance(macros, dict):
        return 55
    calories = _extract_number(macros.get("calories"))
    protein = _extract_number(macros.get("protein"))
    fat = _extract_number(macros.get("fat"))
    carbs = _extract_number(macros.get("carbs"))

    calories_score = 80
    if calories > 0:
        if 380 <= calories <= 700:
            calories_score = 95
        elif 250 <= calories < 380 or 700 < calories <= 850:
            calories_score = 78
        else:
            calories_score = 60

    protein_score = 70
    if protein >= 30:
        protein_score = 95
    elif protein >= 20:
        protein_score = 85
    elif protein >= 12:
        protein_score = 72
    else:
        protein_score = 58

    fat_penalty = 0 if fat <= 28 else min(18, int((fat - 28) * 0.8))
    carbs_penalty = 0 if carbs <= 75 else min(12, int((carbs - 75) * 0.4))
    score = int(round((calories_score * 0.45) + (protein_score * 0.55))) - fat_penalty - carbs_penalty
    return max(0, min(score, 100))


def _extract_number(value: Any) -> float:
    text = str(value or "")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return 0.0
    return float(match.group(1))
