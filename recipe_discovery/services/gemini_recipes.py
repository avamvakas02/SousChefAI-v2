import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils.text import slugify

from users.models import UserProfile

from recipe_discovery.recipe_ingredients import filter_household_staples
from recipe_discovery.services.image_providers import _persist_generated_recipe_image
from recipe_discovery.services.recommendations import _normalize_tokens


def _extract_json_object(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL)
    if fenced:
        raw = fenced.group(1).strip()

    candidates = [raw]
    object_start = raw.find("{")
    object_end = raw.rfind("}")
    if object_start >= 0 and object_end > object_start:
        candidates.append(raw[object_start : object_end + 1])
    array_start = raw.find("[")
    array_end = raw.rfind("]")
    if array_start >= 0 and array_end > array_start:
        candidates.append(raw[array_start : array_end + 1])

    parsed = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            break
        except (json.JSONDecodeError, ValueError):
            continue

    if isinstance(parsed, list):
        parsed = {"recipes": parsed}
    if not isinstance(parsed, dict):
        return None

    if "recipes" in parsed:
        return parsed

    stack = list(parsed.values())
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            if "recipes" in value:
                return value
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return None


def _safe_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _slugify_recipe_id(title: str, idx: int) -> str:
    slug = slugify(title or "")
    return slug or f"recipe-{idx}"


def _difficulty_mix_for_skill(skill_level: str) -> list[str]:
    mixes = {
        UserProfile.SkillLevel.BEGINNER: ["Easy", "Easy", "Easy", "Medium"],
        UserProfile.SkillLevel.INTERMEDIATE: ["Easy", "Medium", "Medium", "Hard"],
        UserProfile.SkillLevel.ADVANCED: ["Easy", "Medium", "Hard", "Hard"],
    }
    return mixes.get(skill_level, mixes[UserProfile.SkillLevel.BEGINNER])


def _gemini_generate_recipe_cards(
    pantry_names: list[str],
    user_goal: str = "",
    skill_level: str = UserProfile.SkillLevel.BEGINNER,
) -> tuple[list[dict], str | None]:
    api_key = (getattr(settings, "GEMINI_API_KEY", "") or "").strip()
    if not api_key or not pantry_names:
        return [], "Missing Gemini API key or pantry ingredients."

    model = getattr(settings, "GEMINI_RECIPE_MODEL", "") or "gemini-1.5-flash"
    pantry_csv = ", ".join(pantry_names[:35])
    difficulty_mix = _difficulty_mix_for_skill(skill_level)
    difficulty_line = ", ".join(difficulty_mix)
    extra_goal = (user_goal or "").strip()
    goal_line = (
        f"User preference to honor: {extra_goal}"
        if extra_goal
        else "User preference to honor: fast, practical meals."
    )
    prompt = (
        "You are a meal-planning assistant. Return ONLY JSON and no markdown.\n"
        "JSON schema:\n"
        "{"
        '"recipes":[{"title":"string","description":"string","time_minutes":number,"difficulty":"Easy|Medium|Hard",'
        '"portions":number,"needed":["ingredient1"],"steps":["step1"]}]'
        "}\n"
        "Rules:\n"
        "- Return exactly 4 recipes.\n"
        "- Include a short description (1-2 sentences) for each recipe.\n"
        "- Use pantry ingredients as much as possible.\n"
        "- Do not include household staples like water, salt, or black pepper in needed ingredients.\n"
        "- Keep ingredients realistic and concise (max 12).\n"
        "- Keep steps practical (12-16 short steps).\n"
        f"- Match this exact difficulty sequence for the 4 recipes: {difficulty_line}.\n"
        "- Output valid JSON only.\n"
        f"Pantry ingredients: {pantry_csv}\n"
        f"{goal_line}\n"
    )
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7,
        },
    }
    req = Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "SousChefAI/1.0 (+gemini-recipe-generator)",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            err_payload = json.loads(exc.read().decode("utf-8"))
            err_message = (err_payload.get("error") or {}).get("message") or str(exc)
        except (json.JSONDecodeError, ValueError, OSError):
            err_message = str(exc)
        return [], f"Gemini API error ({exc.code}): {err_message}"
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return [], "Network or response parsing error while calling Gemini."

    text_candidates: list[str] = []
    for candidate in payload.get("candidates") or []:
        for part in (candidate.get("content") or {}).get("parts") or []:
            text = (part.get("text") or "").strip()
            if text:
                text_candidates.append(text)

    parsed_object = None
    for text in text_candidates:
        parsed_object = _extract_json_object(text)
        if parsed_object:
            break
    if not parsed_object:
        return [], "Gemini returned no valid JSON payload."

    raw_recipes = parsed_object.get("recipes")
    if not isinstance(raw_recipes, list):
        return [], "Gemini response JSON did not include a recipes list."

    pantry_tokens = _normalize_tokens(pantry_names)
    cards: list[dict] = []
    used_image_sources: set[str] = set()
    used_image_hashes: set[str] = set()
    for idx, row in enumerate(raw_recipes[:4], start=1):
        if not isinstance(row, dict):
            continue
        title = (row.get("title") or "").strip()
        description = (row.get("description") or "").strip()
        needed = filter_household_staples(
            [str(x).strip() for x in (row.get("needed") or []) if str(x).strip()]
        )[:12]
        steps = [str(x).strip() for x in (row.get("steps") or []) if str(x).strip()][:16]
        if not title or not needed or not steps:
            continue
        if not description:
            description = " ".join(steps[:2]).strip()
        difficulty = difficulty_mix[len(cards)]

        ingredient_tokens = _normalize_tokens(needed)
        overlap = pantry_tokens.intersection(ingredient_tokens)
        score = len(overlap) / max(len(ingredient_tokens), 1)
        recipe_id = _slugify_recipe_id(title, idx)
        card = {
            "id": recipe_id,
            "title": title,
            "description": description,
            "time_minutes": _safe_int(row.get("time_minutes"), 30, 5, 180),
            "difficulty": difficulty,
            "portions": _safe_int(row.get("portions"), 2, 1, 12),
            "needed": needed,
            "steps": steps,
            "pantry_match": int(round(score * 100)),
        }
        card["image_url"] = _persist_generated_recipe_image(
            card["title"],
            pantry_names,
            card["id"],
            card["needed"],
            used_image_sources,
            used_image_hashes,
        )
        cards.append(card)
    if not cards:
        return [], "Gemini response format was incomplete."
    return cards, None


def _ensure_minimum_steps(steps: list[str], minimum: int = 12) -> list[str]:
    normalized = [str(step).strip() for step in (steps or []) if str(step).strip()]
    if len(normalized) >= minimum:
        return normalized

    fallback_steps = [
        "Gather and measure all ingredients before you begin cooking.",
        "Preheat the cooking equipment so temperature is stable before adding food.",
        "Prepare all vegetables and aromatics so cooking flows smoothly.",
        "Season the main ingredients evenly for balanced flavor.",
        "Start cooking on medium heat and adjust gradually to avoid burning.",
        "Stir and monitor texture regularly to keep even cooking.",
        "Taste and adjust salt, pepper, and acidity as needed.",
        "Lower the heat and let flavors combine for a few minutes.",
        "Check doneness of proteins and vegetables before finishing.",
        "Rest the dish briefly so juices and flavors settle.",
        "Plate the dish neatly and add final garnish if available.",
        "Serve warm and store leftovers in an airtight container.",
    ]
    for fallback in fallback_steps:
        if len(normalized) >= minimum:
            break
        normalized.append(fallback)
    return normalized[: max(minimum, len(normalized))]


def _build_recipe_description(recipe: dict) -> str:
    description = str(recipe.get("description") or "").strip()
    if description:
        return description

    needed = filter_household_staples(
        [str(item).strip() for item in (recipe.get("needed") or []) if str(item).strip()]
    )
    steps = [str(step).strip() for step in (recipe.get("steps") or []) if str(step).strip()]
    if needed:
        ingredient_preview = ", ".join(needed[:3])
        if len(needed) > 3:
            ingredient_preview = f"{ingredient_preview}, and more"
        if steps:
            return f"A pantry-first dish using {ingredient_preview}. {steps[0]}"
        return f"A pantry-first dish using {ingredient_preview}."
    if steps:
        return steps[0]
    return "A pantry-first recipe generated by SousChefAI."


