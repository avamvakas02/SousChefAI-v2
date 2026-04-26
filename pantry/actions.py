from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect

from .catalog_service import (
    _catalog_display_name,
    _pantry_inventory_ajax,
    _redirect_after_zone_catalog_post,
    _redirect_pantry_inventory_after_change,
    _remaining_in_pantry_view_count,
)
from .ingredient_service import get_zone_by_slug, lookup_preset
from .models import PantryItem


def _delete_item(request):
    # main idea: remove one pantry row owned by the current user.
    # filtering by user is important so one user can never delete another user pantry item.
    raw_id = (request.POST.get("item_id") or "").strip()
    try:
        item_pk = int(raw_id)
    except (TypeError, ValueError):
        if _pantry_inventory_ajax(request):
            return JsonResponse({"ok": False, "message": "Invalid item selection."}, status=400)
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


def _quick_add(request):
    # main idea: add a catalog ingredient to the user pantry.
    # preset_key comes from the template, then lookup_preset turns it into category and name.
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


def _quick_remove(request):
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


def _delete_bulk(request):
    pk_list = []
    for raw_id in request.POST.getlist("item_id"):
        try:
            pk_list.append(int(raw_id))
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


def _handle_pantry_post(request):
    # main idea: all pantry forms send an action value here.
    # this keeps the views smaller because add, remove, and bulk delete share one dispatcher.
    """Dispatch pantry POST actions away from the view layer."""
    handlers = {
        "delete": _delete_item,
        "quick_add": _quick_add,
        "quick_remove": _quick_remove,
        "delete_bulk": _delete_bulk,
    }
    handler = handlers.get((request.POST.get("action") or "").strip())
    return handler(request) if handler else None


