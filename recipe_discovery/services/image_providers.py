import base64
import hashlib
import json
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from django.conf import settings
from django.templatetags.static import static


def _ai_recipe_image_url(title: str, pantry_names: list[str], recipe_id: str) -> str:
    """
    Build an AI-generated food image URL for each recipe card.
    Uses a public text-to-image endpoint so each generated recipe has its own image.
    """
    pantry_hint = ", ".join(pantry_names[:4]) if pantry_names else "fresh ingredients"
    prompt = (
        f"{title}, plated food photography, realistic lighting, high detail, "
        f"ingredients include {pantry_hint}, no text, no watermark"
    )
    encoded = quote_plus(prompt)
    seed = int(hashlib.sha1(recipe_id.encode("utf-8")).hexdigest()[:8], 16) % 100000
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=768&height=512&seed={seed}&nologo=true"
    )


def _download_image_bytes(image_url: str, timeout: int = 8) -> bytes | None:
    try:
        req = Request(
            image_url,
            headers={"User-Agent": "SousChefAI/1.0 (+recipe-image-fetcher)"},
        )
        with urlopen(req, timeout=timeout) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            payload = response.read()
            if not payload or "image" not in content_type:
                return None
            return payload
    except (URLError, TimeoutError, OSError, ValueError):
        return None


def _recipe_search_queries(title: str, needed: list[str]) -> list[str]:
    core = [x.strip() for x in needed[:3] if (x or "").strip()]
    queries = [
        f"{title} plated dish",
        f"{title} food photography",
    ]
    if core:
        queries.append(f"{' '.join(core)} plated meal")
        queries.append(f"{core[0]} recipe plated food")
    return queries


def _pexels_recipe_image_urls(title: str, needed: list[str]) -> list[str]:
    api_key = (getattr(settings, "PEXELS_API_KEY", "") or "").strip()
    if not api_key:
        return []
    all_urls: list[str] = []
    for q in _recipe_search_queries(title, needed):
        query = quote_plus(q)
        endpoint = f"https://api.pexels.com/v1/search?query={query}&per_page=8&orientation=landscape"
        req = Request(
            endpoint,
            headers={
                "Authorization": api_key,
                "User-Agent": "SousChefAI/1.0 (+pexels-recipe-search)",
            },
        )
        try:
            with urlopen(req, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
            continue
        for photo in payload.get("photos", []):
            src = photo.get("src") or {}
            image_url = src.get("large2x") or src.get("large") or src.get("medium")
            if image_url and image_url not in all_urls:
                all_urls.append(image_url)
    return all_urls


def _unsplash_recipe_image_urls(title: str, needed: list[str]) -> list[str]:
    access_key = (getattr(settings, "UNSPLASH_ACCESS_KEY", "") or "").strip()
    if not access_key:
        return []
    all_urls: list[str] = []
    for q in _recipe_search_queries(title, needed):
        query = quote_plus(q)
        endpoint = (
            "https://api.unsplash.com/search/photos"
            f"?query={query}&per_page=8&orientation=landscape&client_id={access_key}"
        )
        req = Request(
            endpoint,
            headers={"User-Agent": "SousChefAI/1.0 (+unsplash-recipe-search)"},
        )
        try:
            with urlopen(req, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
            continue
        for result in payload.get("results", []):
            urls = result.get("urls") or {}
            image_url = urls.get("regular") or urls.get("small")
            if image_url and image_url not in all_urls:
                all_urls.append(image_url)
    return all_urls


def _gemini_generate_image_bytes(
    title: str, pantry_names: list[str], needed: list[str], uniqueness_tag: str = ""
) -> bytes | None:
    api_key = (getattr(settings, "GEMINI_API_KEY", "") or "").strip()
    if not api_key:
        return None

    model = (
        getattr(settings, "GEMINI_IMAGE_MODEL", "")
        or "gemini-2.0-flash-preview-image-generation"
    )
    pantry_hint = ", ".join(pantry_names[:4]) if pantry_names else "fresh ingredients"
    must_include = ", ".join(needed[:4]) if needed else pantry_hint
    uniqueness_line = (
        f"Uniqueness tag: {uniqueness_tag}. Use a clearly different plating angle/composition from other variants."
        if uniqueness_tag
        else ""
    )
    prompt = (
        f"Create a realistic close-up plated food photo for the exact dish: {title}. "
        f"Dish ingredients must visually match: {must_include}. "
        f"Available pantry context: {pantry_hint}. "
        "No people, no hands, no kitchen tools, no collage. "
        "Single dish only, appetizing restaurant presentation, natural light, "
        "clean neutral background, no text, no watermark. "
        f"{uniqueness_line}"
    )
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    req = Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "SousChefAI/1.0 (+gemini-image-generator)",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=20) as response:
            payload = response.read()
        parsed = json.loads(payload.decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None

    candidates = parsed.get("candidates") or []
    for candidate in candidates:
        parts = (candidate.get("content") or {}).get("parts") or []
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data") or {}
            encoded = inline.get("data")
            if not encoded:
                continue
            try:
                return base64.b64decode(encoded)
            except (ValueError, TypeError):
                continue
    return None


def _persist_generated_recipe_image(
    title: str,
    pantry_names: list[str],
    recipe_id: str,
    needed: list[str],
    used_image_sources: set[str],
    used_image_hashes: set[str],
) -> str:
    """
    Returns a URL consumable by templates.
    Stock providers return their hosted image URLs directly because production
    does not serve runtime files written under MEDIA_ROOT.
    """
    media_dir = Path(settings.MEDIA_ROOT) / "generated_recipes"
    media_dir.mkdir(parents=True, exist_ok=True)

    safe_slug = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in recipe_id.lower())
    safe_slug = "-".join(part for part in safe_slug.split("-") if part) or "recipe"
    suffix = hashlib.sha1(f"{recipe_id}-{uuid.uuid4()}".encode("utf-8")).hexdigest()[:16]
    filename = f"{safe_slug}_{suffix}.png"
    destination = media_dir / filename

    payload = None
    provider = (getattr(settings, "RECIPE_IMAGE_PROVIDER", "gemini") or "gemini").lower()
    if provider in {"fallback", "static", "none"}:
        return static("images/hero-image.jpg")

    if provider == "gemini":
        for attempt in range(4):
            candidate = _gemini_generate_image_bytes(
                title,
                pantry_names,
                needed,
                uniqueness_tag=f"{recipe_id}-variant-{attempt + 1}",
            )
            if not candidate:
                continue
            fingerprint = hashlib.sha1(candidate).hexdigest()
            if fingerprint in used_image_hashes:
                continue
            used_image_hashes.add(fingerprint)
            payload = candidate
            break

    if payload is None:
        pexels_candidates = (
            _pexels_recipe_image_urls(title, needed)
            if provider in {"gemini", "pexels", "stock", "auto"}
            else []
        )
        unsplash_candidates = (
            _unsplash_recipe_image_urls(title, needed)
            if provider in {"gemini", "unsplash", "stock", "auto"}
            else []
        )
        source_candidates = pexels_candidates + unsplash_candidates
        for image_source_url in source_candidates:
            if image_source_url in used_image_sources:
                continue
            used_image_sources.add(image_source_url)
            return image_source_url

    if payload is None and provider in {"pollinations", "ai"}:
        for attempt in range(4):
            seeded_id = recipe_id if attempt == 0 else f"{recipe_id}-fallback-{attempt + 1}"
            image_url = _ai_recipe_image_url(title, pantry_names, seeded_id)
            if image_url in used_image_sources:
                continue
            used_image_sources.add(image_url)
            return image_url
    if payload is None:
        return static("images/hero-image.jpg")

    try:
        destination.write_bytes(payload)
        base_url = settings.MEDIA_URL.rstrip("/")
        return f"{base_url}/generated_recipes/{filename}"
    except OSError:
        return static("images/hero-image.jpg")


