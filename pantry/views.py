from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import PantryItemForm
from .models import PantryItem


@login_required
@require_http_methods(["GET", "POST"])
def pantry_view(request):
    category_filter = (request.GET.get("category") or "").strip()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "delete":
            item = get_object_or_404(
                PantryItem,
                pk=request.POST.get("item_id"),
                user=request.user,
            )
            item.delete()
            messages.success(request, "Removed from your pantry.")
            return redirect("pantry")

        form = PantryItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            item.save()
            messages.success(request, "Added to your pantry.")
            return redirect("pantry")
    else:
        form = PantryItemForm()

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

    return render(
        request,
        "pantry/pantry.html",
        {
            "form": form,
            "items": items,
            "category_filter": category_filter,
            "category_rows": category_rows,
        },
    )
