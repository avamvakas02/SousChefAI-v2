from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
import importlib.util

from subscriptions.models import CustomerSubscription
from subscriptions.permissions import require_plan
from subscriptions.quota import PLAN_VISITOR, effective_plan_for_request
from subscriptions.quota import merge_anonymous_recipe_usage

from .forms import AccountSettingsForm
from .models import UserProfile


def _safe_post(request, key: str) -> str:
    val = request.POST.get(key, "")
    if val is None:
        return ""
    return str(val).strip()


def _safe_next(request) -> str:
    """Internal redirect path after login (avoids open redirects)."""
    raw = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if raw.startswith("/") and not raw.startswith("//"):
        return raw
    return ""

def _social_auth_enabled() -> bool:
    return bool(getattr(settings, "ALLAUTH_ENABLED", False))


def _google_social_auth_enabled() -> bool:
    if not _social_auth_enabled():
        return False

    if importlib.util.find_spec("allauth.socialaccount.providers.google") is None:
        return False

    google_settings = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}).get("google", {})
    if google_settings.get("APP"):
        return True

    try:
        from allauth.socialaccount.models import SocialApp
    except Exception:
        return False

    try:
        site_id = int(getattr(settings, "SITE_ID", 1))
    except (TypeError, ValueError):
        site_id = 1

    return SocialApp.objects.filter(provider="google", sites__id=site_id).exists()


def _default_auth_backend() -> str:
    backends = getattr(settings, "AUTHENTICATION_BACKENDS", ())
    if isinstance(backends, (list, tuple)) and backends:
        return str(backends[0])
    return "django.contrib.auth.backends.ModelBackend"


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        nxt = _safe_next(request)
        return redirect(nxt or "/")

    social_auth_enabled = _social_auth_enabled()
    google_social_auth_enabled = _google_social_auth_enabled()
    login_ctx = {
        "social_auth_enabled": social_auth_enabled,
        "google_social_auth_enabled": google_social_auth_enabled,
        "next": _safe_next(request),
    }

    if request.method == "GET":
        return render(request, "users/login.html", login_ctx)

    username = _safe_post(request, "username")
    password = request.POST.get("password") or ""
    user = authenticate(request, username=username, password=password)
    if user is None:
        messages.error(request, "Invalid username or password.")
        return render(request, "users/login.html", login_ctx)

    if not request.session.session_key:
        request.session.save()
    pre_session_key = request.session.session_key
    auth_login(request, user)
    merge_anonymous_recipe_usage(user, pre_session_key)
    messages.success(request, "Welcome back!")
    nxt = _safe_next(request)
    return redirect(nxt or "/")


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect(request.GET.get("next") or "/")

    social_auth_enabled = _social_auth_enabled()
    google_social_auth_enabled = _google_social_auth_enabled()
    if request.method == "GET":
        return render(
            request,
            "users/register.html",
            {
                "social_auth_enabled": social_auth_enabled,
                "google_social_auth_enabled": google_social_auth_enabled,
            },
        )

    username = _safe_post(request, "username")
    first_name = _safe_post(request, "first_name")
    last_name = _safe_post(request, "last_name")
    email = _safe_post(request, "email")
    skill_level = _safe_post(request, "skill_level") or UserProfile.SkillLevel.BEGINNER
    password1 = request.POST.get("password1") or ""
    password2 = request.POST.get("password2") or ""

    if not username:
        messages.error(request, "Please choose an alias (username).")
        return render(
            request,
            "users/register.html",
            {
                "social_auth_enabled": social_auth_enabled,
                "google_social_auth_enabled": google_social_auth_enabled,
            },
        )

    if User.objects.filter(username__iexact=username).exists():
        messages.error(request, "That alias (username) is already taken.")
        return render(
            request,
            "users/register.html",
            {
                "social_auth_enabled": social_auth_enabled,
                "google_social_auth_enabled": google_social_auth_enabled,
            },
        )

    if password1 != password2:
        messages.error(request, "Passwords do not match.")
        return render(
            request,
            "users/register.html",
            {
                "social_auth_enabled": social_auth_enabled,
                "google_social_auth_enabled": google_social_auth_enabled,
            },
        )

    if len(password1) < 8:
        messages.error(request, "Password must be at least 8 characters long.")
        return render(
            request,
            "users/register.html",
            {
                "social_auth_enabled": social_auth_enabled,
                "google_social_auth_enabled": google_social_auth_enabled,
            },
        )

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password1,
        first_name=first_name,
        last_name=last_name,
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if skill_level in UserProfile.SkillLevel.values:
        profile.skill_level = skill_level
        profile.save(update_fields=["skill_level", "updated_at"])
    if not request.session.session_key:
        request.session.save()
    pre_session_key = request.session.session_key
    auth_login(request, user, backend=_default_auth_backend())
    merge_anonymous_recipe_usage(user, pre_session_key)
    messages.success(request, "Account created. Welcome!")
    return redirect(request.GET.get("next") or "/")


@login_required
@require_http_methods(["GET", "POST"])
def account_settings(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    customer_sub = CustomerSubscription.objects.filter(user=request.user).first()
    current_plan = effective_plan_for_request(request)
    edit_mode = request.method == "POST" or request.GET.get("edit") == "1"

    if request.method == "POST":
        form = AccountSettingsForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your account settings were updated.")
            return redirect("account_settings")
        messages.error(request, "Please fix the highlighted fields and try again.")
        edit_mode = True
    else:
        form = AccountSettingsForm(
            user=request.user,
            initial={
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
                "birthday": profile.birthday.strftime("%d/%m/%Y") if profile.birthday else "",
                "username": request.user.username,
                "email": request.user.email,
                "skill_level": profile.skill_level,
            },
        )

    account_info = {
        "first_name": request.user.first_name or "Not set",
        "last_name": request.user.last_name or "Not set",
        "username": request.user.username or "Not set",
        "email": request.user.email or "Not set",
        "birthday": profile.birthday.strftime("%d/%m/%Y") if profile.birthday else "Not set",
        "skill_level": profile.get_skill_level_display() or "Not set",
    }

    plan_labels = {
        PLAN_VISITOR: "Visitor",
        CustomerSubscription.Plan.REGULAR: "Regular",
        CustomerSubscription.Plan.PREMIUM: "Premium",
    }
    current_plan_label = plan_labels.get(current_plan, "Visitor")

    billing_label = ""
    if customer_sub and customer_sub.billing_interval:
        billing_label = (
            "Monthly"
            if customer_sub.billing_interval == CustomerSubscription.BillingInterval.MONTH
            else "Yearly"
        )

    current_plan_text = current_plan_label
    if billing_label and current_plan != PLAN_VISITOR:
        current_plan_text = f"{current_plan_label} ({billing_label})"

    # Route plan changes through our pricing page where checkout is guaranteed.
    # Stripe Customer Portal may be configured without plan-switch permissions.
    change_plan_url = reverse("pricing")

    return render(
        request,
        "users/account_settings.html",
        {
            "form": form,
            "edit_mode": edit_mode,
            "account_info": account_info,
            "current_plan_text": current_plan_text,
            "change_plan_url": change_plan_url,
        },
    )


@login_required
@require_POST
def logout_view(request):
    auth_logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("/")


@login_required
@require_POST
def delete_account(request):
    user = request.user
    username = user.username
    auth_logout(request)
    user.delete()
    messages.success(request, f"Your account '{username}' has been permanently deleted.")
    return redirect("/")


@login_required
@require_plan(CustomerSubscription.Plan.REGULAR)
def profile_settings_menu(request):
    return render(request, "users/profile_settings_menu.html")


@login_required
@require_http_methods(["GET", "POST"])
def password_change_view(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            updated_user = form.save()
            update_session_auth_hash(request, updated_user)
            messages.success(request, "Your password has been updated successfully.")
            return redirect("password_change")
        messages.error(request, "Please fix the highlighted fields and try again.")
    else:
        form = PasswordChangeForm(request.user)

    return render(request, "users/password_change.html", {"form": form})