import re

from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse

from .ingredient_service import get_zone_by_slug, ingredient_image_url, lookup_preset, resolve_icon
from .models import PantryItem


def canonicalize_ingredient_name(value: str) -> str:
    """
    Temporary local normalizer while recipes app is removed.
    Keeps pantry grouping resilient without cross-app imports.
    """
    lowered = (value or "").strip().lower()
    if not lowered:
        return ""
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    if lowered.endswith("es") and len(lowered) > 3:
        lowered = lowered[:-2]
    elif lowered.endswith("s") and len(lowered) > 2:
        lowered = lowered[:-1]
    return lowered


def _owned_names_lower(user):
    return {
        (n or "").strip().lower()
        for n in PantryItem.objects.filter(user=user).values_list("name", flat=True)
        if (n or "").strip()
    }


def _dedupe_name_key(name: str) -> str:
    """
    Normalize names for catalog dedupe.
    Collapses cosmetic variants like:
    - "Penne Pasta" vs "Penne Pasta (Pasta)"
    - punctuation/case differences
    """
    lowered = (name or "").strip().lower()
    if not lowered:
        return ""
    lowered = re.sub(r"\s*\([^)]*\)\s*", " ", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _presets_for_zone(user, zone):
    # main idea: this prepares the ingredient cards for one catalog zone.
    # it removes duplicate cards and marks ingredients the user already has.
    owned = _owned_names_lower(user)
    rows = []
    # API results can contain duplicates under different ids/names.
    # Deduplicate by display name and by thumbnail to avoid repeated catalog cards.
    seen_names = set()
    seen_image_urls = set()
    for key in zone["keys"]:
        parsed = lookup_preset(key)
        if not parsed:
            continue
        _, name = parsed
        name_norm = (name or "").strip().lower()
        # Keep all source variants visible in catalog (e.g. beef brisket, minced beef).
        # Canonical matching is for pantry equivalence, not UI card collapsing.
        dedupe_key = _dedupe_name_key(name_norm)
        if not dedupe_key or dedupe_key in seen_names:
            continue

        img_url = ingredient_image_url(name)
        if img_url and img_url in seen_image_urls:
            continue

        seen_names.add(dedupe_key)
        if img_url:
            seen_image_urls.add(img_url)
        rows.append(
            {
                "key": key,
                "name": name,
                "icon": resolve_icon(key, name),
                "image_url": img_url,
                "already_added": name_norm in owned,
            }
        )
    return rows


_GROUP_ALIASES = (
    ("tomatoes", ("tomato", "tomatoes")),
    ("apples", ("apple", "apples")),
    ("onions", ("onion", "onions")),
    ("potatoes", ("potato", "potatoes")),
    ("peppers", ("pepper", "peppers", "chili", "chillies", "chilies")),
    ("lemons", ("lemon", "lemons")),
    ("limes", ("lime", "limes")),
    ("bananas", ("banana", "bananas")),
    ("mushrooms", ("mushroom", "mushrooms")),
    ("beans", ("bean", "beans")),
    ("lettuce", ("lettuce",)),
    ("basil", ("basil",)),
    ("garlic", ("garlic",)),
    ("carrots", ("carrot", "carrots")),
    ("asparagus", ("asparagus",)),
    ("eggs", ("egg", "eggs")),
    ("milk", ("milk",)),
    ("cheese", ("cheese", "cheddar", "mozzarella", "feta", "parmesan")),
    ("chicken", ("chicken",)),
    ("beef", ("beef",)),
    ("pork", ("pork", "bacon", "ham")),
    ("fish", ("fish", "salmon", "tuna", "cod", "sardine", "anchovy", "trout")),
    ("oils", ("oil", "olive oil", "vegetable oil")),
    ("vinegars", ("vinegar", "vinegars")),
    ("rice", ("rice",)),
    ("pasta", ("pasta",)),
    ("flour", ("flour",)),
    ("sugar", ("sugar",)),
    ("salt", ("salt",)),
)
CATALOG_INITIAL_VISIBLE = 60
CATALOG_SHOW_MORE_STEP = 30

_CATALOG_CATEGORY_ROWS = (
    ("produce", "Produce"),
    ("dairy_proteins", "Dairy & Proteins"),
    ("pantry_staples", "Pantry Staples"),
)


def _group_heading_for_name(name: str) -> str:
    """
    Return a human-friendly group heading for an ingredient name.
    Example: "Baby Plum Tomatoes" -> "Tomatoes"
    """
    lowered = (name or "").strip().lower()
    if not lowered:
        return "Other ingredients"

    # Normalize punctuation/hyphen variants for alias matching.
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    tokens = [t for t in lowered.split() if t]
    if not tokens:
        return "Other ingredients"

    token_set = set(tokens)
    for heading, aliases in _GROUP_ALIASES:
        if any(alias in lowered or alias in token_set for alias in aliases):
            return heading.title()

    # Fallback: use canonical ingredient family when available ("baby squid" -> "Squid").
    canonical = canonicalize_ingredient_name(name or "")
    if canonical:
        return canonical.title()
    first = tokens[0]
    return first.capitalize()


def _group_presets(rows):
    groups = {}
    for row in rows:
        heading = _group_heading_for_name(row.get("name", ""))
        row["display_name"] = _display_name_for_heading(row.get("name", ""), heading)
        if heading not in groups:
            groups[heading] = []
        groups[heading].append(row)
    grouped_rows = []
    for heading in sorted(groups.keys(), key=lambda h: h.lower()):
        items = sorted(
            groups[heading],
            key=lambda r: (r.get("display_name") or r.get("name") or "").lower(),
        )
        grouped_rows.append({"heading": heading, "items": items})
    return grouped_rows


def _display_name_for_heading(name: str, heading: str) -> str:
    """
    Keep source-provided card labels as-is (e.g. "Name (Type)").
    Group headings still organize rows, but item labels are not reshaped.
    """
    raw = (name or "").strip()
    if not raw:
        return (heading or "").strip()
    return raw


def _catalog_display_name(stored_name: str) -> str:
    """Match catalog card labels: same rules as preset display_name."""
    heading = _group_heading_for_name(stored_name)
    return _display_name_for_heading(stored_name, heading)


def _quick_add_groups(catalog_lookup: dict, owned_names: set[str]) -> list[dict]:
    # main idea: this builds the searchable quick add list on the pantry home page.
    # it groups ingredients by simple headings so the ui is easier to browse.
    """Build grouped quick-add cards for pantry home (same structure as catalog cards)."""
    by_name = {}
    for key, payload in catalog_lookup.items():
        if not payload or len(payload) < 2:
            continue
        name = (payload[1] or "").strip()
        if not name:
            continue
        name_key = name.lower()
        dedupe_key = _dedupe_name_key(name)
        if dedupe_key in by_name:
            continue
        heading = _group_heading_for_name(name)
        by_name[dedupe_key] = {
            "key": key,
            "name": name,
            "display_name": _display_name_for_heading(name, heading),
            "heading": heading,
            "icon": resolve_icon(key, name),
            "image_url": ingredient_image_url(name),
            "already_added": name_key in owned_names,
        }
    groups = {}
    for row in by_name.values():
        heading = row["heading"]
        if heading not in groups:
            groups[heading] = []
        groups[heading].append(row)
    grouped_rows = []
    for heading in sorted(groups.keys(), key=lambda h: h.lower()):
        items = sorted(groups[heading], key=lambda r: (r.get("display_name") or "").lower())
        grouped_rows.append({"heading": heading, "items": items})
    return grouped_rows


def _redirect_after_zone_catalog_post(request) -> HttpResponseRedirect:
    """
    After any catalog zone POST (add/remove, success or validation redirect).
    Stay on the same ingredient catalog when ``return_zone`` is present so users
    can repeat actions. No URL fragment so the browser does not jump scroll.
    """
    slug = (request.POST.get("return_zone") or "").strip()
    if slug and get_zone_by_slug(slug):
        return redirect("pantry_zone", slug=slug)
    return redirect("pantry")


def _categories_for_catalog_filter(filter_value: str) -> tuple[str, ...]:
    # the visible filters are broader than the database categories.
    # for example dairy and proteins are one ui filter but separate stored categories.
    v = (filter_value or "").strip()
    if v == "produce":
        return (PantryItem.Category.PRODUCE,)
    if v == "dairy_proteins":
        return (PantryItem.Category.DAIRY, PantryItem.Category.PROTEINS)
    if v == "pantry_staples":
        return (PantryItem.Category.PANTRY, PantryItem.Category.SPICES)
    # Backward-compatible support for old/raw category query params.
    valid_raw = {c for c, _ in PantryItem.Category.choices}
    if v in valid_raw:
        return (v,)
    return ()


def _catalog_category_label_for_item(category_value: str) -> str:
    if category_value == PantryItem.Category.PRODUCE:
        return "Produce"
    if category_value in (PantryItem.Category.DAIRY, PantryItem.Category.PROTEINS):
        return "Dairy & Proteins"
    if category_value in (PantryItem.Category.PANTRY, PantryItem.Category.SPICES):
        return "Pantry Staples"
    return dict(PantryItem.Category.choices).get(category_value, "Other")


def _redirect_pantry_inventory_after_change(request) -> HttpResponseRedirect:
    """Return to pantry list preserving category filter; fragment lands on the inventory block."""
    cat = (request.GET.get("category") or request.POST.get("return_category") or "").strip()
    base = reverse("pantry")
    frag = "#pantry-inventory-heading"
    if _categories_for_catalog_filter(cat):
        return HttpResponseRedirect(f"{base}?category={cat}{frag}")
    return HttpResponseRedirect(f"{base}{frag}")


def _pantry_inventory_ajax(request) -> bool:
    # this tells the backend if the browser expects json instead of a redirect.
    # the javascript sends this header when removing items without a full page reload.
    """True when client expects JSON (fetch / XHR), not an HTML redirect."""
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
        return True
    accept = (request.headers.get("Accept") or request.META.get("HTTP_ACCEPT") or "").lower()
    return "application/json" in accept


def _remaining_in_pantry_view_count(request) -> int:
    """Item count for the current pantry list filter (GET category or POST return_category)."""
    category_filter = (request.GET.get("category") or request.POST.get("return_category") or "").strip()
    qs = PantryItem.objects.filter(user=request.user)
    raw_categories = _categories_for_catalog_filter(category_filter)
    if raw_categories:
        qs = qs.filter(category__in=raw_categories)
    return qs.count()


