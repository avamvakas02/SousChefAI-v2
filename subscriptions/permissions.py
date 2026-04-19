from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect

from .models import CustomerSubscription
from .quota import PLAN_VISITOR, effective_plan

_PLAN_RANK = {
    PLAN_VISITOR: 0,
    CustomerSubscription.Plan.REGULAR: 1,
    CustomerSubscription.Plan.PREMIUM: 2,
}


def has_required_plan(user, required_plan: str) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    current_plan = effective_plan(user)
    return _PLAN_RANK.get(current_plan, 0) >= _PLAN_RANK.get(required_plan, 0)


def require_plan(required_plan: str, *, api: bool = False):
    """
    Enforce subscription tier checks for feature-gated views.
    `api=True` returns JSON 403 responses instead of HTML redirects.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            current_plan = effective_plan(request.user)
            if has_required_plan(request.user, required_plan):
                return view_func(request, *args, **kwargs)

            message = "This feature requires a Regular or Premium plan. Upgrade to continue."
            if api:
                return JsonResponse(
                    {
                        "error": message,
                        "required_plan": required_plan,
                        "current_plan": current_plan,
                        "upgrade_url": "/pricing/",
                    },
                    status=403,
                )

            messages.warning(request, message)
            return redirect("pricing")

        return _wrapped

    return decorator
