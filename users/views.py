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

@require_http_methods(["GET", "POST"])
def login_register(request):
    if request.user.is_authenticated:
        return redirect(request.GET.get("next") or "/")

    try:
        social_auth_enabled = importlib.util.find_spec("allauth") is not None
    except ModuleNotFoundError:
        social_auth_enabled = False

    if request.method == "GET":
        return render(
            request,
            "users/login.html",
            {"active_tab": "login", "social_auth_enabled": social_auth_enabled},
        )

    form_type = _safe_post(request, "form_type") or (
        "register" if request.POST.get("password1") else "login"
    )

    if form_type == "register":
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
                "users/login.html",
                {"active_tab": "register", "social_auth_enabled": social_auth_enabled},
            )

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, "That alias (username) is already taken.")
            return render(
                request,
                "users/login.html",
                {"active_tab": "register", "social_auth_enabled": social_auth_enabled},
            )

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return render(
                request,
                "users/login.html",
                {"active_tab": "register", "social_auth_enabled": social_auth_enabled},
            )

        if len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(
                request,
                "users/login.html",
                {"active_tab": "register", "social_auth_enabled": social_auth_enabled},
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=first_name,
            last_name=last_name,
        )
        # Create/update dedicated SQL row for this user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if skill_level in UserProfile.SkillLevel.values:
            profile.skill_level = skill_level
            profile.save(update_fields=["skill_level", "updated_at"])
        auth_login(request, user)
        messages.success(request, "Account created. Welcome!")
        return redirect(request.GET.get("next") or "/")

    # login
    username = _safe_post(request, "username")
    password = request.POST.get("password") or ""
    user = authenticate(request, username=username, password=password)
    if user is None:
        messages.error(request, "Invalid username or password.")
        return render(
            request,
            "users/login.html",
            {"active_tab": "login", "social_auth_enabled": social_auth_enabled},
        )

    auth_login(request, user)
    messages.success(request, "Welcome back!")
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