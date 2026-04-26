from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("recipe_discovery", "0001_savedrecipe_state"),
        ("pages", "0002_savedrecipe"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="savedrecipe",
                    name="unique_saved_recipe_per_user",
                ),
                migrations.DeleteModel(
                    name="SavedRecipe",
                ),
            ],
        ),
    ]
