from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
import re

from .ingredient_service import (
    get_catalog,
    get_zone_by_slug,
    ingredient_image_url,
    lookup_preset,
    resolve_icon,
)
from .models import PantryItem


def _owned_names_lower(user):
    return {
        n.lower()
        for n in PantryItem.objects.filter(user=user).values_list("name", flat=True)
    }


def _presets_for_zone(user, zone):
    owned = _owned_names_lower(user)
    rows = []
    # API results can contain duplicates (same ingredient under different ids).
    # Deduplicate by display name (and image URL when available) to prevent repeated tiles in the template.
    seen_names = set()
    seen_images = set()
    for key in zone["keys"]:
        parsed = lookup_preset(key)
        if not parsed:
            continue
        _, name = parsed
        name_norm = (name or "").strip().lower()
        if not name_norm or name_norm in seen_names:
            continue

        img_url = ingredient_image_url(name)
        if img_url and img_url in seen_images:
            # Sometimes the catalog contains near-duplicates that differ in name
            # but resolve to the same thumbnail (same TheMealDB slug).
            continue

        seen_names.add(name_norm)
        if img_url:
            seen_images.add(img_url)
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
CATALOG_INITIAL_VISIBLE = 14
CATALOG_SHOW_MORE_STEP = 15


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

    # Fallback: group by first word so nearby variants still cluster.
    first = tokens[0]
    return first.capitalize()


def _group_presets(rows):
    groups = {}
    order = []
    for row in rows:
        heading = _group_heading_for_name(row.get("name", ""))
        row["display_name"] = _display_name_for_heading(row.get("name", ""), heading)
        if heading not in groups:
            groups[heading] = []
            order.append(heading)
        groups[heading].append(row)
    return [{"heading": heading, "items": groups[heading]} for heading in order]


def _display_name_for_heading(name: str, heading: str) -> str:
    """
    Normalize card labels to "<Heading> (<variant>)" where possible.
    Example: "Baby Plum Tomatoes" -> "Tomatoes (Baby Plum)"
    """
    raw = (name or "").strip()
    if not raw:
        return heading

    heading_clean = (heading or "").strip()
    if not heading_clean:
        return raw

    raw_lower = raw.lower()
    head_lower = heading_clean.lower()

    if raw_lower == head_lower:
        return heading_clean

    variant = raw
    if raw_lower.endswith(" " + head_lower):
        variant = raw[: -(len(head_lower) + 1)].strip(" -_,")
    elif raw_lower.startswith(head_lower + " "):
        variant = raw[len(head_lower) + 1 :].strip(" -_,")

    if not variant or variant.lower() == head_lower:
        return heading_clean
    return f"{heading_clean} ({variant})"


def _catalog_display_name(stored_name: str) -> str:
    """Match catalog card labels: same rules as preset display_name."""
    heading = _group_heading_for_name(stored_name)
    return _display_name_for_heading(stored_name, heading)


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


def _redirect_pantry_inventory_after_change(request) -> HttpResponseRedirect:
    """Return to pantry list preserving category filter; fragment lands on the inventory block."""
    cat = (request.GET.get("category") or request.POST.get("return_category") or "").strip()
    valid_categories = {c for c, _ in PantryItem.Category.choices}
    base = reverse("pantry")
    frag = "#pantry-inventory-heading"
    if cat in valid_categories:
        return HttpResponseRedirect(f"{base}?category={cat}{frag}")
    return HttpResponseRedirect(f"{base}{frag}")


def _pantry_inventory_ajax(request) -> bool:
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
    valid_categories = {c for c, _ in PantryItem.Category.choices}
    qs = PantryItem.objects.filter(user=request.user)
    if category_filter in valid_categories:
        qs = qs.filter(category=category_filter)
    return qs.count()


def _handle_pantry_post(request):
    """Handle POST actions for pantry home and zone pages. Returns redirect or None."""
    action = (request.POST.get("action") or "").strip()
    if action == "delete":
        raw_id = (request.POST.get("item_id") or "").strip()
        try:
            item_pk = int(raw_id)
        except (TypeError, ValueError):
            if _pantry_inventory_ajax(request):
                return JsonResponse(
                    {"ok": False, "message": "Invalid item selection."},
                    status=400,
                )
            messages.error(request, "Could not remove that item.")
            return _redirect_pantry_inventory_after_change(request)
        try:
            item = PantryItem.objects.get(pk=item_pk, user=request.user)
        except PantryItem.DoesNotExist:
            if _pantry_inventory_ajax(request):
                return JsonResponse(
                    {"ok": False, "message": "That item is no longer in your pantry."},
                    status=404,
                )
            messages.warning(request, "That item is no longer in your pantry.")
            return _redirect_pantry_inventory_after_change(request)
        pk_removed = item.pk
        label = _catalog_display_name(item.name)
        slug = (request.POST.get("return_zone") or "").strip()
        item.delete()
        if slug and get_zone_by_slug(slug):
            messages.success(request, f"Removed {label} from your pantry.")
            return redirect("pantry_zone", slug=slug)
        if _pantry_inventory_ajax(request):
            return JsonResponse(
                {
                    "ok": True,
                    "removed_id": pk_removed,
                    "message": f"Removed {label} from your pantry.",
                    "remaining_in_view": _remaining_in_pantry_view_count(request),
                }
            )
        messages.success(request, f"Removed {label} from your pantry.")
        return _redirect_pantry_inventory_after_change(request)

    if action == "quick_add":
        preset_key = (request.POST.get("preset_key") or "").strip()
        quantity = (request.POST.get("quantity") or "").strip()
        parsed = lookup_preset(preset_key)
        if not parsed:
            if _pantry_inventory_ajax(request):
                return JsonResponse(
                    {"ok": False, "message": "That ingredient could not be added."},
                    status=400,
                )
            messages.error(request, "That ingredient could not be added.")
            return _redirect_after_zone_catalog_post(request)
        category, name = parsed
        existing = PantryItem.objects.filter(user=request.user, name__iexact=name).first()
        if existing:
            if quantity:
                existing.quantity = quantity
                existing.save(update_fields=["quantity", "updated_at"])
        else:
            PantryItem.objects.create(
                user=request.user,
                name=name,
                category=category,
                quantity=quantity,
            )
        if _pantry_inventory_ajax(request):
            return JsonResponse({"ok": True, "in_pantry": True})
        return _redirect_after_zone_catalog_post(request)

    if action == "quick_remove":
        preset_key = (request.POST.get("preset_key") or "").strip()
        parsed = lookup_preset(preset_key)
        if not parsed:
            if _pantry_inventory_ajax(request):
                return JsonResponse(
                    {"ok": False, "message": "That ingredient could not be removed."},
                    status=400,
                )
            messages.error(request, "That ingredient could not be removed.")
            return _redirect_after_zone_catalog_post(request)
        _, name = parsed
        PantryItem.objects.filter(user=request.user, name__iexact=name).delete()
        if _pantry_inventory_ajax(request):
            return JsonResponse({"ok": True, "in_pantry": False})
        return _redirect_after_zone_catalog_post(request)

    if action == "delete_bulk":
        raw_ids = request.POST.getlist("item_id")
        pk_list = []
        for x in raw_ids:
            try:
                pk_list.append(int(x))
            except (TypeError, ValueError):
                continue
        if not pk_list:
            if _pantry_inventory_ajax(request):
                return JsonResponse(
                    {"ok": False, "message": "Select at least one item to remove."},
                    status=400,
                )
            messages.warning(request, "Select at least one item to remove.")
            return _redirect_pantry_inventory_after_change(request)
        qs = PantryItem.objects.filter(user=request.user, pk__in=pk_list)
        removed_ids = list(qs.values_list("pk", flat=True))
        count = len(removed_ids)
        qs.delete()
        msg = f"Removed {count} ingredient(s) from your pantry."
        if _pantry_inventory_ajax(request):
            return JsonResponse(
                {
                    "ok": True,
                    "removed_ids": removed_ids,
                    "count": count,
                    "message": msg,
                    "remaining_in_view": _remaining_in_pantry_view_count(request),
                }
            )
        messages.success(request, msg)
        return _redirect_pantry_inventory_after_change(request)

    return None


@login_required
@require_http_methods(["GET", "POST"])
def pantry_home(request):
    if request.method == "POST":
        response = _handle_pantry_post(request)
        if response:
            return response

    category_filter = (request.GET.get("category") or "").strip()

    qs = PantryItem.objects.filter(user=request.user)
    valid_categories = {c for c, _ in PantryItem.Category.choices}
    if category_filter in valid_categories:
        qs = qs.filter(category=category_filter)

    items = list(qs)
    for row in items:
        row.catalog_display_name = _catalog_display_name(row.name)
    counts = {c: 0 for c, _ in PantryItem.Category.choices}
    for row in (
        PantryItem.objects.filter(user=request.user)
        .values("category")
        .annotate(total=Count("id"))
    ):
        counts[row["category"]] = row["total"]

    category_rows = [
        (value, label, counts.get(value, 0))
        for value, label in PantryItem.Category.choices
    ]

    catalog = get_catalog()

    response = render(
        request,
        "pantry/home.html",
        {
            "items": items,
            "category_filter": category_filter,
            "category_rows": category_rows,
            "zones": catalog["zones"],
            "ingredient_catalog_source": catalog.get("source", "static"),
        },
    )
    if request.method == "GET":
        response["Cache-Control"] = "private, no-store, must-revalidate"
        response["Vary"] = "Cookie"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def pantry_zone(request, slug):
    zone = get_zone_by_slug(slug)
    if not zone:
        messages.error(request, "That category was not found.")
        return redirect("pantry")

    if request.method == "POST":
        response = _handle_pantry_post(request)
        if response:
            return response

    presets = _presets_for_zone(request.user, zone)
    preset_groups = _group_presets(presets)

    catalog_template_by_zone = {
        "produce": "pantry/catalogs/produce_catalog.html",
        "dairy_proteins": "pantry/catalogs/dairy_proteins_catalog.html",
        "pantry_staples": "pantry/catalogs/pantry_staples_catalog.html",
    }

    response = render(
        request,
        "pantry/zone.html",
        {
            "zone": zone,
            "presets": presets,
            "preset_groups": preset_groups,
            "catalog_initial_visible": CATALOG_INITIAL_VISIBLE,
            "catalog_show_more_step": CATALOG_SHOW_MORE_STEP,
            "catalog_template": catalog_template_by_zone.get(
                zone["slug"], "pantry/catalogs/pantry_staples_catalog.html"
            ),
        },
    )
    if request.method == "GET":
        response["Cache-Control"] = "private, no-store, must-revalidate"
        response["Vary"] = "Cookie"
    return response
