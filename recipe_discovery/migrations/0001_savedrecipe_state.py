import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("pages", "0002_savedrecipe"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="SavedRecipe",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("recipe_id", models.SlugField(max_length=255)),
                        ("title", models.CharField(max_length=255)),
                        ("description", models.TextField(blank=True)),
                        ("image_url", models.URLField(blank=True, max_length=1000)),
                        ("time_minutes", models.PositiveIntegerField(default=30)),
                        ("difficulty", models.CharField(default="Medium", max_length=32)),
                        ("portions", models.PositiveIntegerField(default=2)),
                        ("pantry_match", models.PositiveIntegerField(default=0)),
                        ("needed", models.JSONField(blank=True, default=list)),
                        ("steps", models.JSONField(blank=True, default=list)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="saved_recipes",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "pages_savedrecipe",
                        "ordering": ["-updated_at"],
                    },
                ),
                migrations.AddConstraint(
                    model_name="savedrecipe",
                    constraint=models.UniqueConstraint(
                        fields=("user", "recipe_id"),
                        name="unique_saved_recipe_per_user",
                    ),
                ),
            ],
        ),
    ]
