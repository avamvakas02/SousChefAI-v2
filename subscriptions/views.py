from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .models import CustomerSubscription
from .stripe_service import (
    _configure_stripe,
    _price_map,
    _safe_origin,
    _stripe_get,
    _stripe_subscription_price_id,
    _sync_subscription_from_stripe_data,
    stripe,
)


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

    # If the user already has an active subscription, changing plans must go
    # through the Stripe Subscription update API -- NOT a new Checkout Session
    # (which would create a second parallel subscription).
    existing_sub = CustomerSubscription.objects.filter(user=request.user).first()
    if (
        existing_sub
        and existing_sub.stripe_subscription_id
        and existing_sub.status == CustomerSubscription.Status.ACTIVE
    ):
        try:
            stripe_sub = stripe.Subscription.retrieve(
                existing_sub.stripe_subscription_id
            )
        except Exception:
            stripe_sub = None

        # If the Stripe record is still active, modify it in place.
        if stripe_sub and _stripe_get(stripe_sub, "status") in (
            "active",
            "trialing",
            "past_due",
        ):
            items = _stripe_get(_stripe_get(stripe_sub, "items"), "data", []) or []
            current_item_id = _stripe_get(items[0], "id") if items else None
            current_price_id = _stripe_subscription_price_id(stripe_sub)

            # No-op if the user picked the plan they already have.
            if current_price_id == price_id:
                return redirect("/pricing/?checkout=current")

            if current_item_id:
                try:
                    updated = stripe.Subscription.modify(
                        existing_sub.stripe_subscription_id,
                        items=[{"id": current_item_id, "price": price_id}],
                        proration_behavior="create_prorations",
                        cancel_at_period_end=False,
                        metadata={
                            "user_id": str(request.user.id),
                            "price_id": price_id,
                        },
                    )
                except Exception as exc:  # pragma: no cover - surface Stripe error
                    return HttpResponseBadRequest(
                        f"Could not change plan: {exc}"
                    )

                # Sync immediately so the user sees the new plan without
                # having to wait for the webhook.
                new_price_id = _stripe_subscription_price_id(updated) or price_id
                _sync_subscription_from_stripe_data(
                    user_id=request.user.id,
                    stripe_customer_id=_stripe_get(updated, "customer")
                    or existing_sub.stripe_customer_id,
                    stripe_subscription_id=_stripe_get(updated, "id")
                    or existing_sub.stripe_subscription_id,
                    stripe_status=_stripe_get(updated, "status") or "active",
                    stripe_price_id=new_price_id,
                    current_period_end_ts=_stripe_get(updated, "current_period_end"),
                )
                return redirect("/pricing/?checkout=success")

    # Otherwise (no active subscription yet, or the Stripe record is gone),
    # fall back to a fresh Checkout Session.
    origin = _safe_origin(request)
    success_url = (
        f"{origin}/subscriptions/checkout/success/"
        "?session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = request.build_absolute_uri("/pricing/?checkout=cancel")
    if not cancel_url.startswith(origin):
        cancel_url = f"{origin}/pricing/?checkout=cancel"

    session_kwargs = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(request.user.id),
        "metadata": {"user_id": str(request.user.id), "price_id": price_id},
    }
    # Reuse the Stripe customer if we already have one, otherwise let
    # Stripe create one from the email. Stripe rejects passing both.
    if existing_sub and existing_sub.stripe_customer_id:
        session_kwargs["customer"] = existing_sub.stripe_customer_id
    else:
        session_kwargs["customer_email"] = request.user.email or None

    session = stripe.checkout.Session.create(**session_kwargs)
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

    session_user_id = str(_stripe_get(session, "client_reference_id") or "").strip()
    if session_user_id and session_user_id != str(request.user.id):
        return redirect("/pricing/?checkout=cancel")

    metadata = _stripe_get(session, "metadata") or {}
    price_id = _stripe_get(metadata, "price_id")
    subscription_obj = _stripe_get(session, "subscription")
    stripe_subscription_id = subscription_obj
    stripe_customer_id = _stripe_get(session, "customer")
    stripe_status = "active"
    current_period_end_ts = None

    if subscription_obj and not isinstance(subscription_obj, str):
        stripe_subscription_id = _stripe_get(subscription_obj, "id") or stripe_subscription_id
        stripe_status = _stripe_get(subscription_obj, "status") or stripe_status
        current_period_end_ts = _stripe_get(subscription_obj, "current_period_end")
        price_id = _stripe_subscription_price_id(subscription_obj) or price_id
    elif subscription_obj:
        try:
            sub = stripe.Subscription.retrieve(subscription_obj)
            stripe_status = _stripe_get(sub, "status") or stripe_status
            current_period_end_ts = _stripe_get(sub, "current_period_end")
            price_id = _stripe_subscription_price_id(sub) or price_id
        except Exception:
            pass

    if not price_id:
        line_items = _stripe_get(_stripe_get(session, "line_items"), "data", []) or []
        if line_items:
            price_id = _stripe_get(_stripe_get(line_items[0], "price"), "id")

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

    event_type = _stripe_get(event, "type")
    data_obj = _stripe_get(_stripe_get(event, "data", {}), "object", {})

    if event_type == "checkout.session.completed":
        metadata = _stripe_get(data_obj, "metadata") or {}
        user_id_raw = _stripe_get(metadata, "user_id") or _stripe_get(
            data_obj, "client_reference_id"
        )
        try:
            user_id = int(user_id_raw)
        except (TypeError, ValueError):
            return HttpResponse(status=200)

        subscription_id = _stripe_get(data_obj, "subscription")
        customer_id = _stripe_get(data_obj, "customer")
        price_id = _stripe_get(metadata, "price_id")
        status = "active"
        period_end = None

        if subscription_id:
            subscription = stripe.Subscription.retrieve(subscription_id)
            status = _stripe_get(subscription, "status")
            period_end = _stripe_get(subscription, "current_period_end")
            items = _stripe_get(_stripe_get(subscription, "items", {}), "data", [])
            if items:
                price_id = _stripe_get(_stripe_get(items[0], "price", {}), "id")

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
        customer_id = _stripe_get(subscription, "customer")
        subscription_id = _stripe_get(subscription, "id")
        status = _stripe_get(subscription, "status")
        period_end = _stripe_get(subscription, "current_period_end")
        items = _stripe_get(_stripe_get(subscription, "items", {}), "data", [])
        price_id = None
        if items:
            price_id = _stripe_get(_stripe_get(items[0], "price", {}), "id")

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
        customer_id = _stripe_get(customer, "id")
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
