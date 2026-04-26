from django.urls import path

from . import views


urlpatterns = [
    path("recipe-discovery/", views.recipe_discovery, name="recipe_discovery"),
    path(
        "recipe-discovery/<slug:recipe_id>/",
        views.recipe_discovery_detail,
        name="recipe_discovery_detail",
    ),
    path(
        "recipe-discovery/<slug:recipe_id>/save/",
        views.save_recipe,
        name="save_recipe",
    ),
    path("saved-recipes/", views.saved_recipes, name="saved_recipes"),
]
