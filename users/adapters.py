from django.core.exceptions import ImproperlyConfigured

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp

from .models import UserProfile


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_app(self, request, provider, client_id=None):
        apps = self.list_apps(request, provider=provider, client_id=client_id)
        if not apps:
            raise SocialApp.DoesNotExist()
        if len(apps) == 1:
            return apps[0]

        # Synthetic apps loaded from SOCIALACCOUNT_PROVIDERS are never saved (pk is None).
        settings_apps = [a for a in apps if a.pk is None]
        db_apps = [a for a in apps if a.pk is not None]

        if len(settings_apps) == 1:
            return settings_apps[0]
        if len(settings_apps) > 1:
            return settings_apps[0]

        if len(db_apps) > 1:
            raise ImproperlyConfigured(
                f"Multiple Social applications are registered for provider {provider!r} on this site. "
                "Open Django Admin → Social applications and keep only one row per provider "
                "(or remove them and use GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET in the environment only)."
            )

        return apps[0]

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        extra_data = sociallogin.account.extra_data or {}
        user.first_name = user.first_name or data.get("first_name") or extra_data.get("given_name", "")
        user.last_name = user.last_name or data.get("last_name") or extra_data.get("family_name", "")
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form=form)
        UserProfile.objects.get_or_create(user=user)
        return user
