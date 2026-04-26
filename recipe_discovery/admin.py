from django.contrib import admin

from .models import SavedRecipe


@admin.register(SavedRecipe)
class SavedRecipeAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "difficulty", "time_minutes", "updated_at")
    list_filter = ("difficulty",)
    search_fields = ("title", "user__username", "user__email")
