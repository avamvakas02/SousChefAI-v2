from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AdminRecipe",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                (
                    "ingredients",
                    models.TextField(help_text="One ingredient per line (or comma-separated)."),
                ),
                (
                    "steps",
                    models.TextField(blank=True, help_text="One step per line (or numbered lines)."),
                ),
                ("time_minutes", models.PositiveIntegerField(default=30)),
                ("difficulty", models.CharField(default="Medium", max_length=32)),
                ("portions", models.PositiveIntegerField(default=2)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["title"]},
        )
    ]
