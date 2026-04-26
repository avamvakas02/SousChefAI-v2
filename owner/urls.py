from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="owner_dashboard"),
    path("users/", views.user_list, name="owner_user_list"),
    path("users/<int:user_id>/", views.user_detail, name="owner_user_detail"),
    path(
        "users/<int:user_id>/subscription/",
        views.update_subscription,
        name="owner_update_subscription",
    ),
    path(
        "users/<int:user_id>/usage/reset/",
        views.reset_current_usage,
        name="owner_reset_current_usage",
    ),
    path(
        "users/<int:user_id>/active/",
        views.set_user_active,
        name="owner_set_user_active",
    ),
    path(
        "users/<int:user_id>/owner-access/",
        views.set_owner_access,
        name="owner_set_owner_access",
    ),
]
