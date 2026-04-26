from django.contrib.auth import login
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from .models import CustomerSubscription, RecipeUsageMonth
from . import quota
from .views import _sync_subscription_from_stripe_data


class StripeLikeObject:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _anon_request():
    rf = RequestFactory()
    request = rf.get("/")

    def get_response(req):
        return HttpResponse()

    SessionMiddleware(get_response).process_request(request)
    request.session.save()
    AuthenticationMiddleware(get_response).process_request(request)
    return request


class QuotaHelpersTests(TestCase):
    def test_visitor_anonymous_cap(self):
        request = _anon_request()
        self.assertTrue(quota.consume_recipe_generation(request))
        self.assertTrue(quota.consume_recipe_generation(request))
        self.assertFalse(quota.consume_recipe_generation(request))
        row = RecipeUsageMonth.objects.get(
            year_month=quota.current_year_month(),
            session_key=request.session.session_key,
            user__isnull=True,
        )
        self.assertEqual(row.count, 2)

    def test_merge_after_login_simulated(self):
        request = _anon_request()
        self.assertTrue(quota.consume_recipe_generation(request))
        self.assertTrue(quota.consume_recipe_generation(request))
        pre_key = request.session.session_key

        user = User.objects.create_user(username="merge_u", password="secret12345")
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        quota.merge_anonymous_recipe_usage(user, pre_key)

        row = RecipeUsageMonth.objects.get(
            user=user, year_month=quota.current_year_month()
        )
        self.assertEqual(row.count, 2)
        self.assertFalse(RecipeUsageMonth.objects.filter(session_key=pre_key).exists())

    def test_premium_unlimited(self):
        user = User.objects.create_user(username="prem", password="secret12345")
        CustomerSubscription.objects.create(
            user=user,
            status=CustomerSubscription.Status.ACTIVE,
            plan=CustomerSubscription.Plan.PREMIUM,
        )
        request = _anon_request()
        request.user = user
        for _ in range(25):
            self.assertTrue(quota.consume_recipe_generation(request))
        row = RecipeUsageMonth.objects.get(
            user=user, year_month=quota.current_year_month()
        )
        self.assertEqual(row.count, 25)

    def test_usage_remaining_regular(self):
        user = User.objects.create_user(username="reg", password="secret12345")
        CustomerSubscription.objects.create(
            user=user,
            status=CustomerSubscription.Status.ACTIVE,
            plan=CustomerSubscription.Plan.REGULAR,
        )
        request = _anon_request()
        request.user = user
        self.assertEqual(quota.usage_remaining(request), 10)
        quota.consume_recipe_generation(request)
        self.assertEqual(quota.usage_remaining(request), 9)


class StripeSubscriptionSyncTests(TestCase):
    def test_trialing_subscription_syncs_as_active_entitlement(self):
        user = User.objects.create_user(username="trial", password="secret12345")

        _sync_subscription_from_stripe_data(
            user_id=user.id,
            stripe_customer_id="cus_trial",
            stripe_subscription_id="sub_trial",
            stripe_status="trialing",
            stripe_price_id=None,
            current_period_end_ts=None,
        )

        sub = CustomerSubscription.objects.get(user=user)
        self.assertEqual(sub.status, CustomerSubscription.Status.ACTIVE)
        self.assertEqual(quota.effective_plan(user), CustomerSubscription.Plan.REGULAR)

    @override_settings(
        STRIPE_SECRET_KEY="sk_test",
        STRIPE_PRICE_REGULAR_MONTHLY="price_regular",
        STRIPE_PRICE_PREMIUM_MONTHLY="price_premium",
        STRIPE_PRICE_PREMIUM_YEARLY="price_premium_year",
    )
    @patch("subscriptions.views.stripe")
    def test_checkout_success_syncs_expanded_stripe_object_price(self, mock_stripe):
        user = User.objects.create_user(username="upgrader", password="secret12345")
        self.client.login(username="upgrader", password="secret12345")
        session = StripeLikeObject(
            client_reference_id=str(user.id),
            customer="cus_123",
            metadata={},
            subscription=StripeLikeObject(
                id="sub_123",
                status="active",
                current_period_end=1893456000,
                items=StripeLikeObject(
                    data=[
                        StripeLikeObject(
                            price=StripeLikeObject(id="price_premium"),
                        )
                    ],
                ),
            ),
            line_items=StripeLikeObject(data=[]),
        )
        mock_stripe.checkout.Session.retrieve.return_value = session

        response = self.client.get(
            reverse("subscriptions_checkout_success"),
            {"session_id": "cs_test_123"},
        )

        self.assertRedirects(response, "/pricing/?checkout=success")
        sub = CustomerSubscription.objects.get(user=user)
        self.assertEqual(sub.status, CustomerSubscription.Status.ACTIVE)
        self.assertEqual(sub.plan, CustomerSubscription.Plan.PREMIUM)
        self.assertEqual(
            sub.billing_interval,
            CustomerSubscription.BillingInterval.MONTH,
        )
        self.assertEqual(quota.effective_plan(user), CustomerSubscription.Plan.PREMIUM)

    @override_settings(
        STRIPE_SECRET_KEY="sk_test",
        STRIPE_PRICE_REGULAR_MONTHLY="price_regular",
        STRIPE_PRICE_PREMIUM_MONTHLY="price_premium",
        STRIPE_PRICE_PREMIUM_YEARLY="price_premium_year",
    )
    @patch("subscriptions.views.stripe")
    def test_checkout_success_url_keeps_stripe_session_placeholder(self, mock_stripe):
        User.objects.create_user(
            username="checkout-user",
            password="secret12345",
            email="checkout@example.com",
        )
        self.client.login(username="checkout-user", password="secret12345")
        mock_stripe.checkout.Session.create.return_value = StripeLikeObject(
            url="https://checkout.stripe.test/session"
        )

        response = self.client.post(
            reverse("subscriptions_checkout"),
            {"price_id": "price_premium"},
            HTTP_HOST="localhost:8080",
        )

        self.assertEqual(response.status_code, 302)
        session_kwargs = mock_stripe.checkout.Session.create.call_args.kwargs
        self.assertEqual(
            session_kwargs["success_url"],
            "http://localhost:8080/subscriptions/checkout/success/?session_id={CHECKOUT_SESSION_ID}",
        )
        self.assertNotIn("%7B", session_kwargs["success_url"])

    @override_settings(
        STRIPE_SECRET_KEY="sk_test",
        STRIPE_PRICE_REGULAR_MONTHLY="price_regular",
        STRIPE_PRICE_PREMIUM_MONTHLY="price_premium",
        STRIPE_PRICE_PREMIUM_YEARLY="price_premium_year",
    )
    @patch("subscriptions.views.stripe")
    def test_checkout_changes_existing_subscription_with_stripe_object(self, mock_stripe):
        user = User.objects.create_user(username="downgrader", password="secret12345")
        CustomerSubscription.objects.create(
            user=user,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            status=CustomerSubscription.Status.ACTIVE,
            plan=CustomerSubscription.Plan.PREMIUM,
            billing_interval=CustomerSubscription.BillingInterval.MONTH,
        )
        self.client.login(username="downgrader", password="secret12345")
        mock_stripe.Subscription.retrieve.return_value = StripeLikeObject(
            id="sub_123",
            status="active",
            customer="cus_123",
            current_period_end=1893456000,
            items=StripeLikeObject(
                data=[
                    StripeLikeObject(
                        id="si_123",
                        price=StripeLikeObject(id="price_premium"),
                    )
                ],
            ),
        )
        mock_stripe.Subscription.modify.return_value = StripeLikeObject(
            id="sub_123",
            status="active",
            customer="cus_123",
            current_period_end=1893456000,
            items=StripeLikeObject(
                data=[
                    StripeLikeObject(
                        id="si_123",
                        price=StripeLikeObject(id="price_regular"),
                    )
                ],
            ),
        )

        response = self.client.post(
            reverse("subscriptions_checkout"),
            {"price_id": "price_regular"},
        )

        self.assertRedirects(response, "/pricing/?checkout=success")
        mock_stripe.Subscription.modify.assert_called_once_with(
            "sub_123",
            items=[{"id": "si_123", "price": "price_regular"}],
            proration_behavior="create_prorations",
            cancel_at_period_end=False,
            metadata={"user_id": str(user.id), "price_id": "price_regular"},
        )
        sub = CustomerSubscription.objects.get(user=user)
        self.assertEqual(sub.plan, CustomerSubscription.Plan.REGULAR)
        self.assertEqual(sub.billing_interval, CustomerSubscription.BillingInterval.MONTH)
