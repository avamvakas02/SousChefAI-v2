from django.urls import path
from . import views

urlpatterns = [
    path("discover/", views.recipe_discovery_page, name="recipe_discovery_page"),
    path("discover/detail/", views.recipe_detail_page, name="recipe_detail_page"),
    path("discover/api/", views.discover_recipes_api, name="discover_recipes_api"),
    path("discover/ask/", views.ask_souschef_api, name="ask_souschef_api"),
    path("favorite/toggle/", views.toggle_favorite, name="toggle_favorite"),
    path("favorite/status/", views.check_favorite_status, name="check_favorite_status"),
]