"""
django-allauth: resolve duplicate SocialApp configuration.

If Google credentials exist in SOCIALACCOUNT_PROVIDERS (env) *and* a Social
application row exists in the admin, list_apps returns two apps and get_app
raises MultipleObjectsReturned. We prefer the settings-defined app so one
source of truth is enough.

If multiple DB-backed apps remain (no settings app), tell the operator to
deduplicate in Admin.
"""

from django.core.exceptions import ImproperlyConfigured

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp


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
