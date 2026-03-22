from django.urls import path

from . import views

urlpatterns = [
    path("", views.pantry_view, name="pantry"),
]
