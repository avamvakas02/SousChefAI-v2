from django.db import models


class AdminRecipe(models.Model):
    title = models.CharField(max_length=255)
    ingredients = models.TextField(
        help_text="One ingredient per line (or comma-separated)."
    )
    steps = models.TextField(
        help_text="One step per line (or numbered lines).",
        blank=True,
    )
    time_minutes = models.PositiveIntegerField(default=30)
    difficulty = models.CharField(max_length=32, default="Medium")
    portions = models.PositiveIntegerField(default=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title

