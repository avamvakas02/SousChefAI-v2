from django.urls import path

from . import views

urlpatterns = [
    path("checkout/", views.checkout, name="subscriptions_checkout"),
    path("checkout/success/", views.checkout_success, name="subscriptions_checkout_success"),
    path("webhook/", views.stripe_webhook, name="subscriptions_webhook"),
    path("portal/", views.customer_portal, name="subscriptions_portal"),
    path("config/", views.stripe_config, name="subscriptions_config"),
]
