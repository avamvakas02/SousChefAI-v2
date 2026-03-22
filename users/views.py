from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .models import UserProfile

import importlib.util


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
    try:
        return importlib.util.find_spec("allauth") is not None
    except ModuleNotFoundError:
        return False


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        nxt = _safe_next(request)
        return redirect(nxt or "/")

    social_auth_enabled = _social_auth_enabled()
    login_ctx = {
        "social_auth_enabled": social_auth_enabled,
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

    auth_login(request, user)
    messages.success(request, "Welcome back!")
    nxt = _safe_next(request)
    return redirect(nxt or "/")


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect(request.GET.get("next") or "/")

    social_auth_enabled = _social_auth_enabled()
    if request.method == "GET":
        return render(request, "users/register.html", {"social_auth_enabled": social_auth_enabled})

    username = _safe_post(request, "username")
    first_name = _safe_post(request, "first_name")
    last_name = _safe_post(request, "last_name")
    email = _safe_post(request, "email")
    skill_level = _safe_post(request, "skill_level") or UserProfile.SkillLevel.BEGINNER
    password1 = request.POST.get("password1") or ""
    password2 = request.POST.get("password2") or ""

    if not username:
        messages.error(request, "Please choose an alias (username).")
        return render(request, "users/register.html", {"social_auth_enabled": social_auth_enabled})

    if User.objects.filter(username__iexact=username).exists():
        messages.error(request, "That alias (username) is already taken.")
        return render(request, "users/register.html", {"social_auth_enabled": social_auth_enabled})

    if password1 != password2:
        messages.error(request, "Passwords do not match.")
        return render(request, "users/register.html", {"social_auth_enabled": social_auth_enabled})

    if len(password1) < 8:
        messages.error(request, "Password must be at least 8 characters long.")
        return render(request, "users/register.html", {"social_auth_enabled": social_auth_enabled})

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
    auth_login(request, user)
    messages.success(request, "Account created. Welcome!")
    return redirect(request.GET.get("next") or "/")


@login_required
def account_settings(request):
    return render(request, "users/account_settings.html")


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