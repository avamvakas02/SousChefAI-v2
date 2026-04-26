from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from pantry.models import PantryItem
from recipe_discovery.models import SavedRecipe
from subscriptions.models import CustomerSubscription, RecipeUsageMonth
from subscriptions.quota import current_year_month
from users.models import UserProfile

OWNER_GROUP_NAME = "Owner"


def is_owner_user(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "is_active", False):
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return user.groups.filter(name=OWNER_GROUP_NAME).exists()


def owner_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = f"/users/login/?next={request.path}"
            return redirect(login_url)
        if not is_owner_user(request.user):
            messages.error(request, "Owner access is required for that page.")
            return redirect("landing")
        return view_func(request, *args, **kwargs)

    return _wrapped


def _owner_user_queryset():
    User = get_user_model()
    return User.objects.select_related("profile", "customer_subscription").order_by(
        "-date_joined"
    )


@owner_required
def dashboard(request):
    User = get_user_model()
    ym = current_year_month()

    subscription_breakdown = list(
        CustomerSubscription.objects.values("plan", "status")
        .annotate(total=Count("id"))
        .order_by("plan", "status")
    )
    current_usage_total = (
        RecipeUsageMonth.objects.filter(year_month=ym).aggregate(total=Sum("count"))[
            "total"
        ]
        or 0
    )

    context = {
        "stats": {
            "total_users": User.objects.count(),
            "active_users": User.objects.filter(is_active=True).count(),
            "owner_users": User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))
            .distinct()
            .count(),
            "active_subscriptions": CustomerSubscription.objects.filter(
                status=CustomerSubscription.Status.ACTIVE
            ).count(),
            "saved_recipes": SavedRecipe.objects.count(),
            "pantry_items": PantryItem.objects.count(),
            "current_usage_total": current_usage_total,
            "current_year_month": ym,
        },
        "recent_users": _owner_user_queryset()[:8],
        "recent_subscriptions": CustomerSubscription.objects.select_related("user")
        .order_by("-current_period_end", "-id")[:8],
        "top_usage_rows": RecipeUsageMonth.objects.select_related("user")
        .filter(year_month=ym)
        .order_by("-count")[:8],
        "subscription_breakdown": subscription_breakdown,
    }
    return render(request, "owner/dashboard.html", context)


@owner_required
def user_list(request):
    query = (request.GET.get("q") or "").strip()
    users = _owner_user_queryset()
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )

    paginator = Paginator(users, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "owner/user_list.html",
        {
            "page_obj": page_obj,
            "query": query,
        },
    )


@owner_required
def user_detail(request, user_id):
    target_user = get_object_or_404(_owner_user_queryset(), pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=target_user)
    subscription = CustomerSubscription.objects.filter(user=target_user).first()
    ym = current_year_month()
    current_usage = RecipeUsageMonth.objects.filter(
        user=target_user,
        year_month=ym,
    ).first()

    context = {
        "target_user": target_user,
        "profile": profile,
        "subscription": subscription,
        "current_usage": current_usage,
        "current_year_month": ym,
        "usage_rows": RecipeUsageMonth.objects.filter(user=target_user).order_by(
            "-year_month"
        )[:12],
        "pantry_items": PantryItem.objects.filter(user=target_user).order_by(
            "category", "name"
        )[:50],
        "saved_recipes": SavedRecipe.objects.filter(user=target_user).order_by(
            "-updated_at"
        )[:20],
        "plan_choices": CustomerSubscription.Plan.choices,
        "status_choices": CustomerSubscription.Status.choices,
        "billing_interval_choices": CustomerSubscription.BillingInterval.choices,
    }
    return render(request, "owner/user_detail.html", context)


@owner_required
@require_POST
def update_subscription(request, user_id):
    target_user = get_object_or_404(get_user_model(), pk=user_id)
    plan = request.POST.get("plan")
    status = request.POST.get("status")
    billing_interval = request.POST.get("billing_interval") or None

    if plan not in CustomerSubscription.Plan.values:
        messages.error(request, "Choose a valid subscription plan.")
        return redirect("owner_user_detail", user_id=target_user.pk)
    if status not in CustomerSubscription.Status.values:
        messages.error(request, "Choose a valid subscription status.")
        return redirect("owner_user_detail", user_id=target_user.pk)
    if billing_interval and billing_interval not in CustomerSubscription.BillingInterval.values:
        messages.error(request, "Choose a valid billing interval.")
        return redirect("owner_user_detail", user_id=target_user.pk)

    subscription, _ = CustomerSubscription.objects.get_or_create(user=target_user)
    subscription.plan = plan
    subscription.status = status
    subscription.billing_interval = billing_interval
    subscription.save(update_fields=["plan", "status", "billing_interval"])
    messages.success(request, f"Updated subscription for {target_user.username}.")
    return redirect("owner_user_detail", user_id=target_user.pk)


@owner_required
@require_POST
def reset_current_usage(request, user_id):
    target_user = get_object_or_404(get_user_model(), pk=user_id)
    row, _ = RecipeUsageMonth.objects.get_or_create(
        user=target_user,
        year_month=current_year_month(),
        defaults={"count": 0},
    )
    row.count = 0
    row.save(update_fields=["count"])
    messages.success(request, f"Reset this month's usage for {target_user.username}.")
    return redirect("owner_user_detail", user_id=target_user.pk)


@owner_required
@require_POST
def set_user_active(request, user_id):
    target_user = get_object_or_404(get_user_model(), pk=user_id)
    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own account from here.")
        return redirect("owner_user_detail", user_id=target_user.pk)
    if target_user.is_superuser and not request.user.is_superuser:
        messages.error(request, "Only a superuser can change a superuser account.")
        return redirect("owner_user_detail", user_id=target_user.pk)

    target_user.is_active = request.POST.get("is_active") == "1"
    target_user.save(update_fields=["is_active"])
    messages.success(request, f"Updated account status for {target_user.username}.")
    return redirect("owner_user_detail", user_id=target_user.pk)


@owner_required
@require_POST
def set_owner_access(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, "Only a superuser can grant or remove owner access.")
        return redirect("owner_user_detail", user_id=user_id)

    target_user = get_object_or_404(get_user_model(), pk=user_id)
    if target_user == request.user:
        messages.error(request, "You cannot remove your own owner access from here.")
        return redirect("owner_user_detail", user_id=target_user.pk)

    target_user.is_staff = request.POST.get("is_staff") == "1"
    target_user.save(update_fields=["is_staff"])
    messages.success(request, f"Updated owner access for {target_user.username}.")
    return redirect(reverse("owner_user_detail", kwargs={"user_id": target_user.pk}))
