from __future__ import annotations

from datetime import datetime, timezone

from django.conf import settings
from django.http import HttpRequest

from .models import CustomerSubscription

try:
    import stripe
except ModuleNotFoundError:  # pragma: no cover
    stripe = None


def _stripe_get(obj, key: str, default=None):
    if obj is None:
        return default
    try:
        getter = getattr(obj, "get", None)
    except AttributeError:
        getter = None
    if callable(getter):
        try:
            return getter(key, default)
        except AttributeError:
            pass
    return getattr(obj, key, default)


def _stripe_subscription_price_id(subscription) -> str | None:
    items = _stripe_get(subscription, "items") or {}
    data = _stripe_get(items, "data", []) or []
    if not data:
        return None
    price = _stripe_get(data[0], "price") or {}
    return _stripe_get(price, "id")


def _price_map() -> dict[str, tuple[str, str]]:
    """
    Stripe Price ID -> (plan, billing_interval)
    """
    return {
        settings.STRIPE_PRICE_REGULAR_MONTHLY: (
            CustomerSubscription.Plan.REGULAR,
            CustomerSubscription.BillingInterval.MONTH,
        ),
        settings.STRIPE_PRICE_PREMIUM_MONTHLY: (
            CustomerSubscription.Plan.PREMIUM,
            CustomerSubscription.BillingInterval.MONTH,
        ),
        settings.STRIPE_PRICE_PREMIUM_YEARLY: (
            CustomerSubscription.Plan.PREMIUM,
            CustomerSubscription.BillingInterval.YEAR,
        ),
    }


def _configure_stripe() -> None:
    if stripe is None:
        raise RuntimeError("The stripe package is not installed.")
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY is missing in environment settings.")
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _safe_origin(request: HttpRequest) -> str:
    scheme = "https" if request.is_secure() else "http"
    host = request.get_host()
    return f"{scheme}://{host}"


def _sync_subscription_from_stripe_data(
    user_id: int,
    stripe_customer_id: str | None,
    stripe_subscription_id: str | None,
    stripe_status: str | None,
    stripe_price_id: str | None,
    current_period_end_ts: int | None,
) -> None:
    customer_sub, _ = CustomerSubscription.objects.get_or_create(user_id=user_id)
    price_map = _price_map()

    plan = customer_sub.plan
    billing_interval = customer_sub.billing_interval
    if stripe_price_id and stripe_price_id in price_map:
        plan, billing_interval = price_map[stripe_price_id]

    if stripe_status in ("active", "trialing"):
        status = CustomerSubscription.Status.ACTIVE
    elif stripe_status == "past_due":
        status = CustomerSubscription.Status.PAST_DUE
    else:
        status = CustomerSubscription.Status.CANCELED

    period_end = None
    if current_period_end_ts:
        period_end = datetime.fromtimestamp(current_period_end_ts, tz=timezone.utc)

    customer_sub.stripe_customer_id = stripe_customer_id or customer_sub.stripe_customer_id
    customer_sub.stripe_subscription_id = (
        stripe_subscription_id or customer_sub.stripe_subscription_id
    )
    customer_sub.status = status
    customer_sub.plan = plan
    customer_sub.billing_interval = billing_interval
    customer_sub.current_period_end = period_end
    customer_sub.save()


