from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("account/", views.account_settings, name="account_settings"),
    path("password/change/", views.password_change_view, name="password_change"),
    path("logout/", views.logout_view, name="logout"),
    path("delete/", views.delete_account, name="delete_account"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/settings/", views.profile_settings_menu, name="profile_settings_menu"),
]
