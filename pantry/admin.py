from django.contrib import admin

from .models import PantryItem


@admin.register(PantryItem)
class PantryItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "user", "quantity", "updated_at")
    list_filter = ("category",)
    search_fields = ("name", "user__username")
    readonly_fields = ("created_at", "updated_at")
