"""django-allauth: merge anonymous recipe quota into the user after any allauth login."""

from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    def login(self, request, user):
        # main idea: login changes the session key, so the old key is saved first.
        # that old key lets anonymous recipe usage merge into the user account.
        from subscriptions.quota import ensure_session_key, merge_anonymous_recipe_usage

        ensure_session_key(request)
        pre_session_key = request.session.session_key
        ret = super().login(request, user)
        merge_anonymous_recipe_usage(user, pre_session_key)
        return ret
