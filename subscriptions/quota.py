"""
Monthly recipe generation quotas (Phase B). Enforce on the server before calling AI.
"""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from django.http import HttpRequest
from django.utils import timezone

from .models import CustomerSubscription, RecipeUsageMonth

PLAN_VISITOR = "visitor"


def current_year_month() -> str:
    return timezone.now().strftime("%Y-%m")


def recipe_quota_for_plan(plan: str) -> int | None:
    """Return max recipes per calendar month, or None for unlimited (premium)."""
    if plan == CustomerSubscription.Plan.PREMIUM:
        return None
    if plan == CustomerSubscription.Plan.REGULAR:
        return 10
    return 2


def effective_plan(user) -> str:
    """
    Paid tier only when subscription row exists and status is active.
    Logged-in users without an active paid plan count as visitor for quotas.
    """
    if not getattr(user, "is_authenticated", False) or isinstance(user, AnonymousUser):
        return PLAN_VISITOR
    if getattr(user, "is_superuser", False):
        return CustomerSubscription.Plan.PREMIUM
    try:
        sub = CustomerSubscription.objects.get(user=user)
    except CustomerSubscription.DoesNotExist:
        return PLAN_VISITOR
    if sub.status != CustomerSubscription.Status.ACTIVE:
        return PLAN_VISITOR
    return sub.plan


def effective_plan_for_request(request: HttpRequest) -> str:
    if not request.user.is_authenticated:
        return PLAN_VISITOR
    return effective_plan(request.user)


def ensure_session_key(request: HttpRequest) -> None:
    if not request.session.session_key:
        request.session.save()


def get_or_create_usage_row(request: HttpRequest) -> RecipeUsageMonth:
    ym = current_year_month()
    if request.user.is_authenticated:
        row, _ = RecipeUsageMonth.objects.get_or_create(
            year_month=ym,
            user=request.user,
            defaults={"count": 0},
        )
        return row

    ensure_session_key(request)
    sk = request.session.session_key
    assert sk is not None
    try:
        return RecipeUsageMonth.objects.get(
            year_month=ym,
            session_key=sk,
            user__isnull=True,
        )
    except RecipeUsageMonth.DoesNotExist:
        try:
            return RecipeUsageMonth.objects.create(
                year_month=ym,
                session_key=sk,
                count=0,
            )
        except IntegrityError:
            return RecipeUsageMonth.objects.get(
                year_month=ym,
                session_key=sk,
                user__isnull=True,
            )


def usage_remaining(request: HttpRequest) -> int | None:
    """
    Remaining generations this month, or None if unlimited.
    """
    plan = effective_plan_for_request(request)
    quota = recipe_quota_for_plan(plan)
    if quota is None:
        return None
    row = get_or_create_usage_row(request)
    return max(0, quota - row.count)


@transaction.atomic
def consume_recipe_generation(request: HttpRequest) -> bool:
    """
    Increment usage if under quota (or unlimited). Returns False if quota exhausted.
    """
    plan = effective_plan_for_request(request)
    quota = recipe_quota_for_plan(plan)
    ym = current_year_month()

    if request.user.is_authenticated:
        row = RecipeUsageMonth.objects.select_for_update().filter(
            year_month=ym,
            user=request.user,
        ).first()
        if row is None:
            try:
                row = RecipeUsageMonth.objects.create(
                    year_month=ym,
                    user=request.user,
                    count=0,
                )
            except IntegrityError:
                row = RecipeUsageMonth.objects.select_for_update().get(
                    year_month=ym,
                    user=request.user,
                )
    else:
        ensure_session_key(request)
        sk = request.session.session_key
        assert sk is not None
        row = RecipeUsageMonth.objects.select_for_update().filter(
            year_month=ym,
            session_key=sk,
            user__isnull=True,
        ).first()
        if row is None:
            try:
                row = RecipeUsageMonth.objects.create(
                    year_month=ym,
                    session_key=sk,
                    count=0,
                )
            except IntegrityError:
                row = RecipeUsageMonth.objects.select_for_update().get(
                    year_month=ym,
                    session_key=sk,
                    user__isnull=True,
                )

    if quota is not None and row.count >= quota:
        return False
    row.count += 1
    row.save(update_fields=["count"])
    return True


@transaction.atomic
def merge_anonymous_recipe_usage(user, pre_login_session_key: str | None) -> None:
    """
    After login, move this month's anonymous counts onto the user row.
    `pre_login_session_key` must be captured before django.contrib.auth.login(),
    because login() may cycle the session key for anonymous sessions.
    """
    if not pre_login_session_key:
        return
    ym = current_year_month()
    try:
        anon_row = RecipeUsageMonth.objects.select_for_update().get(
            year_month=ym,
            session_key=pre_login_session_key,
            user__isnull=True,
        )
    except RecipeUsageMonth.DoesNotExist:
        return

    extra = anon_row.count

    if extra == 0:
        anon_row.delete()
        return

    user_row = RecipeUsageMonth.objects.select_for_update().filter(
        year_month=ym,
        user=user,
    ).first()
    if user_row is None:
        try:
            RecipeUsageMonth.objects.create(
                year_month=ym,
                user=user,
                count=extra,
            )
        except IntegrityError:
            user_row = RecipeUsageMonth.objects.select_for_update().get(
                year_month=ym,
                user=user,
            )
            user_row.count += extra
            user_row.save(update_fields=["count"])
    else:
        user_row.count += extra
        user_row.save(update_fields=["count"])

    anon_row.delete()
