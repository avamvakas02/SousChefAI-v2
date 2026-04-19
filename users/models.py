from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    class SkillLevel(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    birthday = models.DateField(blank=True, null=True)
    skill_level = models.CharField(
        max_length=20, choices=SkillLevel.choices, default=SkillLevel.BEGINNER
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.username} profile"
