from django.contrib import admin

from .models import AdminRecipe


@admin.register(AdminRecipe)
class AdminRecipeAdmin(admin.ModelAdmin):
    list_display = ("title", "difficulty", "time_minutes", "portions", "is_active")
    list_filter = ("difficulty", "is_active")
    search_fields = ("title", "ingredients")
