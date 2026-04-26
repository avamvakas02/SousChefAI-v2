from django.conf import settings
from django.shortcuts import render

from subscriptions.models import CustomerSubscription
from subscriptions.quota import PLAN_VISITOR, effective_plan_for_request


def landing(request):
    return render(request, "landing.html")


def pricing(request):
    current_plan = effective_plan_for_request(request)
    current_plan_billing_interval = None
    if request.user.is_authenticated:
        active_subscription = CustomerSubscription.objects.filter(
            user=request.user,
            status=CustomerSubscription.Status.ACTIVE,
        ).first()
        if active_subscription:
            current_plan_billing_interval = active_subscription.billing_interval

    is_current_visitor = current_plan == PLAN_VISITOR
    is_current_regular = current_plan == CustomerSubscription.Plan.REGULAR
    is_current_premium_monthly = (
        current_plan == CustomerSubscription.Plan.PREMIUM
        and current_plan_billing_interval != CustomerSubscription.BillingInterval.YEAR
    )
    is_current_premium_yearly = (
        current_plan == CustomerSubscription.Plan.PREMIUM
        and current_plan_billing_interval == CustomerSubscription.BillingInterval.YEAR
    )

    return render(
        request,
        "pages/pricing.html",
        {
            "stripe_price_regular_monthly": settings.STRIPE_PRICE_REGULAR_MONTHLY,
            "stripe_price_premium_monthly": settings.STRIPE_PRICE_PREMIUM_MONTHLY,
            "stripe_price_premium_yearly": settings.STRIPE_PRICE_PREMIUM_YEARLY,
            "is_current_visitor": is_current_visitor,
            "is_current_regular": is_current_regular,
            "is_current_premium_monthly": is_current_premium_monthly,
            "is_current_premium_yearly": is_current_premium_yearly,
        },
    )


def about_us(request):
    return render(request, "pages/about-us.html")


def contact_us(request):
    return render(request, "pages/contact-us.html")


def privacy_policy(request):
    return render(request, "pages/privacy-policy.html")
