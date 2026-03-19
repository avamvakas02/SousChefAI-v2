from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_register, name="login"),
    path("account/", views.account_settings, name="account_settings"),
    path("logout/", views.logout_view, name="logout"),
    path("delete/", views.delete_account, name="delete_account"),
]
