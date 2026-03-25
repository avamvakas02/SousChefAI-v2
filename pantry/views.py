from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

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
    for key in zone["keys"]:
        parsed = lookup_preset(key)
        if not parsed:
            continue
        _, name = parsed
        rows.append(
            {
                "key": key,
                "name": name,
                "icon": resolve_icon(key, name),
                "image_url": ingredient_image_url(name),
                "already_added": name.lower() in owned,
            }
        )
    return rows


def _redirect_after_quick_add(request) -> HttpResponseRedirect:
    """Return redirect target after quick_add; respects return_zone hidden field."""
    slug = (request.POST.get("return_zone") or "").strip()
    if slug and get_zone_by_slug(slug):
        return redirect("pantry_zone", slug=slug)
    return redirect("pantry")


def _handle_pantry_post(request):
    """Handle POST actions for pantry home and zone pages. Returns redirect or None."""
    action = request.POST.get("action")
    if action == "delete":
        item = get_object_or_404(
            PantryItem,
            pk=request.POST.get("item_id"),
            user=request.user,
        )
        item.delete()
        messages.success(request, "Removed from your pantry.")
        slug = (request.POST.get("return_zone") or "").strip()
        if slug and get_zone_by_slug(slug):
            return redirect("pantry_zone", slug=slug)
        return redirect("pantry")

    if action == "quick_add":
        preset_key = (request.POST.get("preset_key") or "").strip()
        parsed = lookup_preset(preset_key)
        if not parsed:
            messages.error(request, "That ingredient could not be added.")
            return _redirect_after_quick_add(request)
        category, name = parsed
        if PantryItem.objects.filter(user=request.user, name__iexact=name).exists():
            messages.info(request, f"{name} is already in your pantry.")
        else:
            PantryItem.objects.create(
                user=request.user,
                name=name,
                category=category,
            )
            messages.success(request, f"Added {name}.")
        return _redirect_after_quick_add(request)

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

    return render(
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

    return render(
        request,
        "pantry/zone.html",
        {
            "zone": zone,
            "presets": presets,
        },
    )
