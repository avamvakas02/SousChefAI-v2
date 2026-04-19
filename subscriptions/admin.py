from django.contrib import admin

from .models import CustomerSubscription, RecipeUsageMonth


@admin.register(CustomerSubscription)
class CustomerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "current_period_end")
    list_filter = ("plan", "status")
    search_fields = ("user__username", "user__email", "stripe_customer_id", "stripe_subscription_id")


@admin.register(RecipeUsageMonth)
class RecipeUsageMonthAdmin(admin.ModelAdmin):
    list_display = ("year_month", "user", "session_key", "count")
    list_filter = ("year_month",)
    search_fields = ("session_key", "user__username")
