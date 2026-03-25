from django.urls import path

from . import views

urlpatterns = [
    path("", views.pantry_home, name="pantry"),
    path("zone/<slug>/", views.pantry_zone, name="pantry_zone"),
]
