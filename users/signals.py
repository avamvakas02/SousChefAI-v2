from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    # main idea: every new user gets a profile automatically.
    # recipe generation uses the profile skill level when building prompts.
    if not created:
        return
    UserProfile.objects.get_or_create(user=instance)

