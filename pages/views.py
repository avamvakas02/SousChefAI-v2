from django.conf import settings
from django.shortcuts import render

def landing(request):
    return render(request, 'landing.html')


def pricing(request):
    return render(
        request,
        "pages/pricing.html",
        {
            "stripe_price_regular_monthly": settings.STRIPE_PRICE_REGULAR_MONTHLY,
            "stripe_price_premium_monthly": settings.STRIPE_PRICE_PREMIUM_MONTHLY,
            "stripe_price_premium_yearly": settings.STRIPE_PRICE_PREMIUM_YEARLY,
        },
    )