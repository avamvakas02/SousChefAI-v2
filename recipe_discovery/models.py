from django.conf import settings
from django.db import models


class SavedRecipe(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_recipes",
    )
    recipe_id = models.SlugField(max_length=255)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=1000, blank=True)
    time_minutes = models.PositiveIntegerField(default=30)
    difficulty = models.CharField(max_length=32, default="Medium")
    portions = models.PositiveIntegerField(default=2)
    pantry_match = models.PositiveIntegerField(default=0)
    needed = models.JSONField(default=list, blank=True)
    steps = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pages_savedrecipe"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "recipe_id"],
                name="unique_saved_recipe_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.title}"
