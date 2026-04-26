from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .actions import _handle_pantry_post
from .catalog_service import (
    CATALOG_INITIAL_VISIBLE,
    CATALOG_SHOW_MORE_STEP,
    _CATALOG_CATEGORY_ROWS,
    _catalog_category_label_for_item,
    _catalog_display_name,
    _categories_for_catalog_filter,
    _group_presets,
    _owned_names_lower,
    _presets_for_zone,
    _quick_add_groups,
)
from .ingredient_service import get_catalog, get_zone_by_slug
from .models import PantryItem


@login_required
@require_http_methods(["GET", "POST"])
def pantry_home(request):
    # main idea: this is the pantry dashboard.
    # it handles add/remove form posts first, then rebuilds the list of ingredients for the page.
    if request.method == "POST":
        response = _handle_pantry_post(request)
        if response:
            return response

    # the filter comes from the dropdown in the template.
    # one visible catalog filter can map to more than one database category.
    category_filter = (request.GET.get("category") or "").strip()

    qs = PantryItem.objects.filter(user=request.user)
    raw_categories = _categories_for_catalog_filter(category_filter)
    if raw_categories:
        qs = qs.filter(category__in=raw_categories)

    items = list(qs)
    # before sending ingredients to the template, extra display fields are attached.
    # this is why the table can show clean names and friendly category labels.
    for row in items:
        row.catalog_display_name = _catalog_display_name(row.name)
        row.catalog_category_display = _catalog_category_label_for_item(row.category)
    counts = {key: 0 for key, _ in _CATALOG_CATEGORY_ROWS}
    for row in (
        PantryItem.objects.filter(user=request.user)
        .values("category")
        .annotate(total=Count("id"))
    ):
        cat = row["category"]
        total = row["total"]
        if cat == PantryItem.Category.PRODUCE:
            counts["produce"] += total
        elif cat in (PantryItem.Category.DAIRY, PantryItem.Category.PROTEINS):
            counts["dairy_proteins"] += total
        elif cat in (PantryItem.Category.PANTRY, PantryItem.Category.SPICES):
            counts["pantry_staples"] += total

    category_rows = [
        (value, label, counts.get(value, 0))
        for value, label in _CATALOG_CATEGORY_ROWS
    ]

    owned_names = _owned_names_lower(request.user)
    catalog = get_catalog()
    # quick add is built from the full ingredient catalog.
    # the template uses it to render searchable ingredient cards on the pantry page.
    quick_add_groups = _quick_add_groups(catalog.get("lookup", {}), owned_names)

    response = render(
        request,
        "pantry/home.html",
        {
            "items": items,
            "category_filter": category_filter,
            "category_rows": category_rows,
            "zones": catalog["zones"],
            "quick_add_groups": quick_add_groups,
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
    # main idea: a zone page shows one catalog section, such as produce or pantry staples.
    # the slug chooses the catalog group and the template renders the matching ingredient cards.
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

    response = render(
        request,
        "pantry/zone.html",
        {
            "zone": zone,
            "presets": presets,
            "preset_groups": preset_groups,
            "catalog_initial_visible": CATALOG_INITIAL_VISIBLE,
            "catalog_show_more_step": CATALOG_SHOW_MORE_STEP,
        },
    )
    if request.method == "GET":
        response["Cache-Control"] = "private, no-store, must-revalidate"
        response["Vary"] = "Cookie"
    return response
