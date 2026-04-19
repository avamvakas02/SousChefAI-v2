import json
import os
import re
import uuid
import base64
from pathlib import Path
from typing import Any, Dict, List

import google.generativeai as genai
from django.conf import settings
from pantry.models import PantryItem
from .ingredient_aliases import canonicalize_ingredient_name
from users.models import UserProfile


def discover_pantry_recipes(user, payload: Dict[str, Any]) -> Dict[str, Any]:
    pantry_items = _load_user_pantry_items(user)
    extra_items = _normalize_list(payload.get("extra_items") or [])
    available_for_match = _normalize_list(list(pantry_items) + list(extra_items))

    pantry_only = bool(payload.get("pantry_only", False))
    max_missing = int(payload.get("max_missing", 2))
    goal = (payload.get("goal") or "quick").strip().lower()
    preferences = payload.get("preferences", {})
    requested_count = 5
    user_skill_level = _resolve_user_skill_level(user)
    target_difficulty_mix = _difficulty_mix_for_skill(user_skill_level)

    candidates: List[Dict[str, Any]] = []
    errors: List[str] = []
    gemini_raw_preview = ""
    try:
        candidates, gemini_raw_preview = _generate_with_gemini(
            pantry_items, payload, user_skill_level, target_difficulty_mix
        )
    except Exception as exc:
        errors.append(f"Gemini generation failed: {exc}")

    ranked: List[Dict[str, Any]] = []
    relaxed_ranked: List[Dict[str, Any]] = []
    filtered_reasons: List[str] = []

    for index, recipe in enumerate(candidates, start=1):
        if not isinstance(recipe, dict):
            continue

        flat_ingredients = _flatten_recipe_ingredients(recipe.get("ingredients"))
        if not flat_ingredients:
            filtered_reasons.append(f"Recipe {index}: no usable ingredients list from model.")
            continue

        used_pantry_ingredients, missing_ingredients = _split_used_missing(
            flat_ingredients, available_for_match
        )
        total_ingredients_count = len(flat_ingredients)
        have_count = len(used_pantry_ingredients)
        pantry_match_percent = int((have_count / max(total_ingredients_count, 1)) * 100)

        normalized_recipe = {
            "id": recipe.get("id") or f"gemini_{index}",
            "title": recipe.get("title") or "Untitled recipe",
            "description": recipe.get("description") or "Generated recipe suggestion.",
            "cook_time_minutes": int(recipe.get("cook_time_minutes") or 30),
            "difficulty": recipe.get("difficulty") or "medium",
            "servings": int(recipe.get("servings") or preferences.get("servings", 2)),
            "pantry_match_percent": pantry_match_percent,
            "have_count": have_count,
            "total_ingredients_count": total_ingredients_count,
            "missing_ingredients": missing_ingredients,
            "used_pantry_ingredients": used_pantry_ingredients,
            "why_suggested": recipe.get("why_suggested")
            or f"Goal '{goal}' matched with pantry-first logic.",
            "steps": recipe.get("steps")
            if isinstance(recipe.get("steps"), list)
            else ["Prepare ingredients.", "Cook and serve."],
            "macros": recipe.get("macros", {}),
            "equipment": recipe.get("equipment", []),
            "chef_tip": recipe.get("chef_tip", "Taste as you go and season generously!"),
            "score": round(
                (have_count / max(total_ingredients_count, 1))
                - (0.15 * len(missing_ingredients)),
                4,
            ),
        }
        relaxed_ranked.append(normalized_recipe)

        if pantry_only and missing_ingredients:
            filtered_reasons.append(
                f"Recipe {index}: pantry_only but missing {missing_ingredients[:5]}"
            )
            continue
        if len(missing_ingredients) > max_missing:
            filtered_reasons.append(
                f"Recipe {index}: too many missing ({len(missing_ingredients)} > {max_missing})."
            )
            continue

        ranked.append(normalized_recipe)

    ranked.sort(key=lambda r: r["score"], reverse=True)
    top = _select_recipes_by_skill_mix(ranked, user_skill_level, requested_count)
    was_relaxed = False
    if not top and relaxed_ranked:
        relaxed_ranked.sort(key=lambda r: r["score"], reverse=True)
        top = _select_recipes_by_skill_mix(relaxed_ranked, user_skill_level, requested_count)
        was_relaxed = True

    fallback_message = None
    if not top:
        if not candidates:
            fallback_message = (
                "No recipes returned from the model. Check GEMINI_API_KEY, model name, "
                "and billing. See diagnostics for a raw response preview."
            )
        else:
            fallback_message = (
                f"Every generated recipe was filtered out (pantry_only={pantry_only}, "
                f"max_missing={max_missing}). Try increasing max_missing or toggling pantry_only off."
            )
            errors.extend(filtered_reasons[:5])
            if len(filtered_reasons) > 5:
                errors.append(f"...and {len(filtered_reasons) - 5} more filter reasons.")
    elif was_relaxed:
        fallback_message = (
            "Strict pantry filters removed all recipes. Showing best pantry-matched recipes "
            "with extra missing ingredients."
        )
        errors.append(
            f"Relaxed mode used: strict filter returned 0 results with max_missing={max_missing}."
        )

    if top:
        _attach_generated_images(top, errors)

    return {
        "meta": {
            "used_pantry_count": len(pantry_items),
            "requested_count": requested_count,
            "returned_count": len(top),
            "user_skill_level": user_skill_level,
            "target_difficulty_mix": target_difficulty_mix,
            "pantry_only": pantry_only,
            "max_missing": max_missing,
            "gemini_candidate_count": len(candidates),
            "after_filter_count": len(ranked),
            "relaxed_mode_used": was_relaxed,
        },
        "recipes": top,
        "fallback_message": fallback_message,
        "errors": errors,
        "diagnostics": {
            "gemini_raw_preview": gemini_raw_preview[:1200] if gemini_raw_preview else "",
            "extra_items_count": len(extra_items),
        },
    }


def _attach_generated_images(recipes: List[Dict[str, Any]], errors: List[str]) -> None:
    """Generate and save per-recipe images using Gemini image model."""
    for idx, recipe in enumerate(recipes[:5], start=1):
        try:
            image_url = _generate_and_store_recipe_image(recipe)
            if image_url:
                recipe["image_url"] = image_url
        except Exception as exc:
            errors.append(f"Image generation failed for recipe {idx}: {exc}")


def _generate_and_store_recipe_image(recipe: Dict[str, Any]) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return ""

    genai.configure(api_key=api_key)
    candidate_models = _candidate_image_models()

    title = str(recipe.get("title") or "recipe")
    ingredients = recipe.get("used_pantry_ingredients") or recipe.get("missing_ingredients") or []
    ingredients_preview = ", ".join([str(i) for i in ingredients[:6]])
    prompt = (
        "Create a photorealistic food photograph of this plated dish. "
        f"Dish: {title}. Key ingredients: {ingredients_preview}. "
        "Style: natural light, high detail, editorial food photography, no text, no logos, no watermark."
    )

    image_bytes = b""
    ext = "png"
    last_error = ""
    tried_models: List[str] = []
    for model_name in candidate_models:
        try:
            tried_models.append(model_name)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            image_bytes, ext = _extract_image_from_response(response)
            if image_bytes:
                break
        except Exception as exc:
            last_error = str(exc)
            continue

    if not image_bytes:
        if last_error:
            raise ValueError(
                f"{last_error} | tried_image_models={tried_models or candidate_models}"
            )
        raise ValueError(
            f"No image bytes returned by any Gemini image model. tried_image_models={tried_models or candidate_models}"
        )

    media_root = Path(getattr(settings, "MEDIA_ROOT", Path(settings.BASE_DIR) / "media"))
    out_dir = media_root / "generated_recipes"
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.lower()).strip("_") or "recipe"
    filename = f"{safe_stem}_{uuid.uuid4().hex[:10]}.{ext}"
    output_path = out_dir / filename
    output_path.write_bytes(image_bytes)

    media_url = getattr(settings, "MEDIA_URL", "/media/")
    return f"{media_url}generated_recipes/{filename}"


def _extract_image_from_response(response: Any) -> tuple[bytes, str]:
    """
    Best-effort extraction of image bytes from Gemini response.
    Supports inline_data bytes or base64-like strings.
    """
    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            if not inline_data:
                continue
            raw = getattr(inline_data, "data", None)
            mime = getattr(inline_data, "mime_type", "") or "image/png"
            ext = "png" if "png" in mime else "jpg"
            if isinstance(raw, bytes):
                return raw, ext
            if isinstance(raw, str) and raw:
                try:
                    return base64.b64decode(raw), ext
                except Exception:
                    continue

    return b"", "png"


def _candidate_image_models() -> List[str]:
    """
    Build a robust fallback chain:
    1) explicit env override
    2) known image-generation model names
    3) dynamically discovered Gemini models containing 'image'
    """
    configured_model = os.getenv("GEMINI_IMAGE_MODEL", "").strip()
    known = [
        "gemini-2.0-flash-preview-image-generation",
        "gemini-2.0-flash-exp-image-generation",
        "gemini-1.5-flash",
    ]

    discovered: List[str] = []
    try:
        for m in genai.list_models():
            name = getattr(m, "name", "") or ""
            # m.name often looks like "models/gemini-..."
            short = name.split("/", 1)[1] if "/" in name else name
            if "gemini" in short and "image" in short:
                discovered.append(short)
    except Exception:
        # If model listing fails, keep known fallback list.
        pass

    ordered = [configured_model] + known + discovered
    seen = set()
    out: List[str] = []
    for model_name in ordered:
        if model_name and model_name not in seen:
            seen.add(model_name)
            out.append(model_name)
    return out


def _generate_with_gemini(
    pantry_items: List[str],
    payload: Dict[str, Any],
    user_skill_level: str,
    target_difficulty_mix: Dict[str, int],
) -> tuple[List[Dict[str, Any]], str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_RECIPE_MODEL", "gemini-2.5-flash")
    model = genai.GenerativeModel(model_name)

    max_missing = int(payload.get("max_missing", 2))
    pantry_only = bool(payload.get("pantry_only", False))
    easy_count = int(target_difficulty_mix.get("easy", 0))
    medium_count = int(target_difficulty_mix.get("medium", 0))
    hard_count = int(target_difficulty_mix.get("hard", 0))

    prompt = f"""
You are a pantry-first recipe generator.
Return ONLY valid JSON (no markdown) with top-level key "recipes" containing an array of 5 recipes.

Input:
- pantry_items (use these EXACT strings in the ingredients list whenever possible): {pantry_items}
- goal: {payload.get("goal", "quick")}
- pantry_only: {pantry_only}
- max_missing: {max_missing}
- user_skill_level: {user_skill_level}
- target_difficulty_mix: easy={easy_count}, medium={medium_count}, hard={hard_count}
- preferences: {payload.get("preferences", {})}
- dietary_constraints: {payload.get("dietary_constraints", {})}

Rules:
1) Each recipe's "ingredients" must be an array of strings.
2) Prefer ingredients that appear verbatim in pantry_items (same spelling/casing is not required; match the pantry string).
3) If pantry_only is true, every ingredient must be from pantry_items.
4) If pantry_only is false, you may add at most {max_missing} ingredients NOT in pantry_items per recipe.
5) Keep each recipe to 6-10 ingredients so matching stays realistic.
6) Respect dietary_constraints strictly.
7) You MUST return exactly 5 recipes with this exact difficulty distribution:
   - easy: {easy_count}
   - medium: {medium_count}
   - hard: {hard_count}
8) Use ONLY difficulty values: "easy", "medium", or "hard".
9) steps must be an array of highly detailed instruction strings, where each step explicitly states what to do, cooking times, techniques, and visual cues for doneness.
10) macros must be an object with keys: calories, protein, carbs, fat (use estimated string values like "450 kcal").
11) equipment must be an array of strings listing required kitchen tools.
12) chef_tip must be a professional cooking trick or tip string for the recipe.

Each recipe object must include exactly these keys:
id, title, description, cook_time_minutes, difficulty, servings, ingredients, why_suggested, steps, macros, equipment, chef_tip
"""

    response = model.generate_content(prompt)
    raw_text = ""
    try:
        raw_text = (response.text or "").strip()
    except ValueError:
        # Blocked or empty candidates; summarize finish reasons.
        parts: List[str] = []
        for cand in getattr(response, "candidates", []) or []:
            finish = getattr(getattr(cand, "finish_reason", None), "name", None) or str(
                getattr(cand, "finish_reason", "")
            )
            parts.append(f"finish_reason={finish}")
        raw_text = "; ".join(parts) if parts else "empty_response"

    parsed = _extract_json_object(raw_text)
    recipes = parsed.get("recipes", [])
    out = recipes if isinstance(recipes, list) else []
    out_dicts = [r for r in out if isinstance(r, dict)]
    return out_dicts, raw_text


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*)\s*```$", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    elif text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Gemini returned non-JSON output.")
        return json.loads(text[start : end + 1])


def _flatten_recipe_ingredients(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return _normalize_list([raw])
    if not isinstance(raw, list):
        return []

    out: List[str] = []
    for item in raw:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            name = item.get("name") or item.get("ingredient") or item.get("item")
            if name:
                out.append(str(name))
            else:
                out.append(json.dumps(item, sort_keys=True))
    return _normalize_list(out)


def _load_user_pantry_items(user) -> List[str]:
    rows = PantryItem.objects.filter(user=user).values_list("name", flat=True)
    return _normalize_list(list(rows))


def _normalize_list(items: List[str]) -> List[str]:
    seen = set()
    normalized: List[str] = []
    for item in items:
        clean = " ".join(str(item).strip().lower().split())
        if clean and clean not in seen:
            seen.add(clean)
            normalized.append(clean)
    return normalized


def _match_key(value: str) -> str:
    return canonicalize_ingredient_name(value)


def _split_used_missing(
    recipe_ingredients: List[str], available_items: List[str]
) -> tuple[List[str], List[str]]:
    pantry_norm = _normalize_list(available_items)
    available = set(pantry_norm)
    pantry_key_to_name: Dict[str, str] = {}
    for pan in pantry_norm:
        key = _match_key(pan)
        if key and key not in pantry_key_to_name:
            pantry_key_to_name[key] = pan

    used: List[str] = []
    missing: List[str] = []

    for ingredient in _normalize_list(recipe_ingredients):
        ing_key = _match_key(ingredient)
        if ingredient in available:
            used.append(ingredient)
            continue
        if ing_key and ing_key in pantry_key_to_name:
            used.append(pantry_key_to_name[ing_key])
            continue

        matched = _best_pantry_match(ingredient, pantry_norm)
        if matched:
            used.append(matched)
        else:
            missing.append(ingredient)

    return used, missing


def _best_pantry_match(ingredient: str, pantry_norm: List[str]) -> str:
    """Match recipe line to pantry using exact token overlap (handles 'chicken' vs 'chicken breast')."""
    ing = ingredient.strip().lower()
    if len(ing) < 2:
        return ""

    ing_tokens = [t for t in re.split(r"[^\w]+", ing) if len(t) >= 3]
    best = ""
    best_score = 0

    for pan in pantry_norm:
        pan_l = pan.lower()
        if ing == pan_l:
            return pan
        if ing in pan_l or pan_l in ing:
            score = min(len(ing), len(pan_l))
            if score > best_score:
                best_score = score
                best = pan
            continue

        pan_tokens = [t for t in re.split(r"[^\w]+", pan_l) if len(t) >= 3]
        if not ing_tokens or not pan_tokens:
            continue
        overlap = len(set(ing_tokens) & set(pan_tokens))
        if overlap > best_score:
            best_score = overlap
            best = pan

    return best if best_score > 0 else ""


def _resolve_user_skill_level(user) -> str:
    try:
        profile = getattr(user, "profile", None)
        if profile:
            skill_level = str(profile.skill_level or "").strip().lower()
            if skill_level in UserProfile.SkillLevel.values:
                return skill_level
            if skill_level == "expert":
                return UserProfile.SkillLevel.ADVANCED
    except Exception:
        pass
    return UserProfile.SkillLevel.BEGINNER


def _normalize_difficulty(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"easy", "medium", "hard"}:
        return normalized
    aliases = {
        "beginner": "easy",
        "simple": "easy",
        "intermediate": "medium",
        "moderate": "medium",
        "advanced": "hard",
        "expert": "hard",
        "difficult": "hard",
    }
    return aliases.get(normalized, "medium")


def _difficulty_mix_for_skill(skill_level: str) -> Dict[str, int]:
    normalized_skill = str(skill_level or "").strip().lower()
    if normalized_skill == UserProfile.SkillLevel.INTERMEDIATE:
        return {"easy": 1, "medium": 3, "hard": 1}
    if normalized_skill in {UserProfile.SkillLevel.ADVANCED, "expert"}:
        return {"easy": 1, "medium": 1, "hard": 3}
    return {"easy": 3, "medium": 2, "hard": 0}


def _select_recipes_by_skill_mix(
    recipes: List[Dict[str, Any]], skill_level: str, requested_count: int
) -> List[Dict[str, Any]]:
    if not recipes:
        return []

    by_difficulty: Dict[str, List[Dict[str, Any]]] = {"easy": [], "medium": [], "hard": []}
    for recipe in recipes:
        bucket = _normalize_difficulty(recipe.get("difficulty"))
        recipe["difficulty"] = bucket
        by_difficulty[bucket].append(recipe)

    target_mix = _difficulty_mix_for_skill(skill_level)
    selected: List[Dict[str, Any]] = []
    selected_keys = set()
    selected_counts: Dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}

    def recipe_key(recipe: Dict[str, Any]) -> str:
        return str(recipe.get("id") or f"{recipe.get('title', 'untitled')}::{recipe.get('score', 0)}")

    def take_from_bucket(level: str, count: int) -> None:
        if count <= 0:
            return
        for recipe in by_difficulty.get(level, []):
            key = recipe_key(recipe)
            if key in selected_keys:
                continue
            selected.append(recipe)
            selected_keys.add(key)
            selected_counts[level] = selected_counts.get(level, 0) + 1
            if selected_counts.get(level, 0) >= count:
                break

    # First pass: enforce target skill-based mix as much as possible.
    for level in ("easy", "medium", "hard"):
        take_from_bucket(level, target_mix.get(level, 0))

    # Second pass: backfill with highest-scored remaining recipes.
    if len(selected) < requested_count:
        for recipe in recipes:
            key = recipe_key(recipe)
            if key in selected_keys:
                continue
            selected.append(recipe)
            selected_keys.add(key)
            if len(selected) >= requested_count:
                break

    return selected[:requested_count]
