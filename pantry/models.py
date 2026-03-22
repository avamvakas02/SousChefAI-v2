from django.conf import settings
from django.db import models


class PantryItem(models.Model):
    class Category(models.TextChoices):
        PRODUCE = "produce", "Produce"
        DAIRY = "dairy", "Dairy"
        PROTEINS = "proteins", "Proteins & Meat"
        PANTRY = "pantry", "Pantry & Grains"
        SPICES = "spices", "Spices & Oils"
        FROZEN = "frozen", "Frozen"
        OTHER = "other", "Other"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pantry_items",
    )
    name = models.CharField(max_length=200)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    quantity = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "name"]
        indexes = [
            models.Index(fields=["user", "category"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_category_display()})"
