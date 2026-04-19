from __future__ import annotations

from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .models import CustomerSubscription

try:
    import stripe
except ModuleNotFoundError:  # pragma: no cover
    stripe = None


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

    if stripe_status == "active":
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


@login_required
@require_http_methods(["GET", "POST"])
def checkout(request: HttpRequest) -> HttpResponse:
    try:
        _configure_stripe()
    except RuntimeError as exc:
        return HttpResponseBadRequest(str(exc))

    raw_price_id = request.POST.get("price_id") or request.GET.get("price_id")
    price_id = (raw_price_id or "").strip()
    price_map = _price_map()
    if not price_id or price_id not in price_map:
        return HttpResponseBadRequest("Invalid price_id.")

    origin = _safe_origin(request)
    success_url = request.build_absolute_uri(
        "/subscriptions/checkout/success/?session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = request.build_absolute_uri("/pricing/?checkout=cancel")
    if not success_url.startswith(origin):
        success_url = (
            f"{origin}/subscriptions/checkout/success/?session_id={{CHECKOUT_SESSION_ID}}"
        )
    if not cancel_url.startswith(origin):
        cancel_url = f"{origin}/pricing/?checkout=cancel"

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(request.user.id),
        metadata={"user_id": str(request.user.id), "price_id": price_id},
        customer_email=request.user.email or None,
    )
    return redirect(session.url, permanent=False)


@login_required
@require_http_methods(["GET"])
def checkout_success(request: HttpRequest) -> HttpResponse:
    """
    Sync subscription immediately after Stripe Checkout success redirect.
    This avoids relying solely on webhooks in local/dev environments.
    """
    session_id = (request.GET.get("session_id") or "").strip()
    if not session_id:
        return redirect("/pricing/?checkout=cancel")

    try:
        _configure_stripe()
    except RuntimeError:
        return redirect("/pricing/?checkout=cancel")

    try:
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=["subscription", "line_items.data.price"],
        )
    except Exception:
        return redirect("/pricing/?checkout=cancel")

    session_user_id = str(session.get("client_reference_id") or "").strip()
    if session_user_id and session_user_id != str(request.user.id):
        return redirect("/pricing/?checkout=cancel")

    metadata = session.get("metadata") or {}
    price_id = metadata.get("price_id")
    stripe_subscription_id = session.get("subscription")
    stripe_customer_id = session.get("customer")
    stripe_status = "active"
    current_period_end_ts = None

    subscription_obj = session.get("subscription")
    if isinstance(subscription_obj, dict):
        stripe_subscription_id = subscription_obj.get("id") or stripe_subscription_id
        stripe_status = subscription_obj.get("status") or stripe_status
        current_period_end_ts = subscription_obj.get("current_period_end")
        items = (subscription_obj.get("items") or {}).get("data", [])
        if items:
            price_id = (items[0].get("price") or {}).get("id") or price_id
    elif stripe_subscription_id:
        try:
            sub = stripe.Subscription.retrieve(stripe_subscription_id)
            stripe_status = sub.get("status") or stripe_status
            current_period_end_ts = sub.get("current_period_end")
            items = (sub.get("items") or {}).get("data", [])
            if items:
                price_id = (items[0].get("price") or {}).get("id") or price_id
        except Exception:
            pass

    if not price_id:
        line_items = (session.get("line_items") or {}).get("data", [])
        if line_items:
            price_id = (line_items[0].get("price") or {}).get("id")

    _sync_subscription_from_stripe_data(
        user_id=request.user.id,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        stripe_status=stripe_status,
        stripe_price_id=price_id,
        current_period_end_ts=current_period_end_ts,
    )
    return redirect("/pricing/?checkout=success")


@csrf_exempt
@require_POST
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    try:
        _configure_stripe()
    except RuntimeError:
        return HttpResponse(status=500)

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    if not webhook_secret:
        return HttpResponse(status=500)

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    event_type = event.get("type")
    data_obj = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        metadata = data_obj.get("metadata") or {}
        user_id_raw = metadata.get("user_id") or data_obj.get("client_reference_id")
        try:
            user_id = int(user_id_raw)
        except (TypeError, ValueError):
            return HttpResponse(status=200)

        subscription_id = data_obj.get("subscription")
        customer_id = data_obj.get("customer")
        price_id = metadata.get("price_id")
        status = "active"
        period_end = None

        if subscription_id:
            subscription = stripe.Subscription.retrieve(subscription_id)
            status = subscription.get("status")
            period_end = subscription.get("current_period_end")
            items = subscription.get("items", {}).get("data", [])
            if items:
                price_id = items[0].get("price", {}).get("id")

        _sync_subscription_from_stripe_data(
            user_id=user_id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            stripe_status=status,
            stripe_price_id=price_id,
            current_period_end_ts=period_end,
        )

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        subscription = data_obj
        customer_id = subscription.get("customer")
        subscription_id = subscription.get("id")
        status = subscription.get("status")
        period_end = subscription.get("current_period_end")
        items = subscription.get("items", {}).get("data", [])
        price_id = None
        if items:
            price_id = items[0].get("price", {}).get("id")

        customer_sub = CustomerSubscription.objects.filter(
            stripe_subscription_id=subscription_id
        ).first()
        if customer_sub is None and customer_id:
            customer_sub = CustomerSubscription.objects.filter(
                stripe_customer_id=customer_id
            ).first()
        if customer_sub is not None:
            _sync_subscription_from_stripe_data(
                user_id=customer_sub.user_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                stripe_status=status,
                stripe_price_id=price_id,
                current_period_end_ts=period_end,
            )

    return HttpResponse(status=200)


@login_required
def customer_portal(request: HttpRequest) -> HttpResponse:
    try:
        _configure_stripe()
    except RuntimeError as exc:
        return HttpResponseBadRequest(str(exc))

    customer_sub, _ = CustomerSubscription.objects.get_or_create(user=request.user)
    customer_id = customer_sub.stripe_customer_id

    if not customer_id:
        customer = stripe.Customer.create(
            email=request.user.email or None,
            metadata={"user_id": str(request.user.id)},
        )
        customer_id = customer.get("id")
        customer_sub.stripe_customer_id = customer_id
        customer_sub.save(update_fields=["stripe_customer_id"])

    portal_session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=request.build_absolute_uri("/users/account/"),
    )
    return redirect(portal_session.url, permanent=False)


def stripe_config(request: HttpRequest) -> HttpResponse:
    """
    Small helper endpoint for templates/JS if needed later.
    """
    data = {
        "regular_monthly": settings.STRIPE_PRICE_REGULAR_MONTHLY,
        "premium_monthly": settings.STRIPE_PRICE_PREMIUM_MONTHLY,
        "premium_yearly": settings.STRIPE_PRICE_PREMIUM_YEARLY,
    }
    return JsonResponse(data)
