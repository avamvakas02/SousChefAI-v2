from django.conf import settings
from django.db import models
from django.db.models import Q


class CustomerSubscription(models.Model):
    """One row per user; Stripe IDs filled after first checkout."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"

    class Plan(models.TextChoices):
        REGULAR = "regular", "Regular"
        PREMIUM = "premium", "Premium"

    class BillingInterval(models.TextChoices):
        MONTH = "month", "Month"
        YEAR = "year", "Year"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_subscription",
    )
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.CANCELED,
    )
    plan = models.CharField(
        max_length=16,
        choices=Plan.choices,
        default=Plan.REGULAR,
    )
    billing_interval = models.CharField(
        max_length=8,
        choices=BillingInterval.choices,
        null=True,
        blank=True,
    )
    current_period_end = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "customer subscription"
        verbose_name_plural = "customer subscriptions"

    def __str__(self) -> str:
        return f"{self.user} — {self.get_plan_display()} ({self.get_status_display()})"


class RecipeUsageMonth(models.Model):
    """Monthly recipe generation count, keyed by user OR anonymous session (never both)."""

    year_month = models.CharField(
        max_length=7,
        help_text='Calendar month as "YYYY-MM".',
    )
    count = models.PositiveIntegerField(default=0)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="recipe_usage_months",
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        verbose_name = "recipe usage (month)"
        verbose_name_plural = "recipe usage (by month)"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, session_key__isnull=True)
                    | Q(user__isnull=True, session_key__isnull=False)
                ),
                name="recipe_usage_month_user_xor_session",
            ),
            models.UniqueConstraint(
                fields=("year_month", "user"),
                condition=Q(user__isnull=False),
                name="recipe_usage_month_unique_user_month",
            ),
            models.UniqueConstraint(
                fields=("year_month", "session_key"),
                condition=Q(session_key__isnull=False),
                name="recipe_usage_month_unique_session_month",
            ),
        ]

    def __str__(self) -> str:
        if self.user_id is not None:
            who = f"user {self.user_id}"
        else:
            who = f"session ...{self.session_key[-6:]}" if self.session_key else "?"
        return f"{self.year_month} | {who} | {self.count}"
