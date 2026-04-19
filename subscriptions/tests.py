from django.contrib.auth import login
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from .models import CustomerSubscription, RecipeUsageMonth
from . import quota


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
