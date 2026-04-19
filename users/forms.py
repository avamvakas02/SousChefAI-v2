from django import forms
from django.contrib.auth.models import User

from .models import UserProfile


class AccountSettingsForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    birthday = forms.DateField(
        required=False,
        input_formats=["%d/%m/%Y", "%Y-%m-%d"],
    )
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=False)
    skill_level = forms.ChoiceField(choices=UserProfile.SkillLevel.choices, required=True)

    def __init__(self, *args, user: User, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise forms.ValidationError("Alias (username) is required.")

        exists = User.objects.filter(username__iexact=username).exclude(pk=self.user.pk).exists()
        if exists:
            raise forms.ValidationError("That alias (username) is already taken.")
        return username

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip()

    def save(self):
        user = self.user
        user.first_name = (self.cleaned_data.get("first_name") or "").strip()
        user.last_name = (self.cleaned_data.get("last_name") or "").strip()
        user.username = self.cleaned_data["username"]
        user.email = self.cleaned_data.get("email", "")
        user.save(update_fields=["first_name", "last_name", "username", "email"])

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.birthday = self.cleaned_data.get("birthday")
        profile.skill_level = self.cleaned_data["skill_level"]
        profile.save(update_fields=["birthday", "skill_level", "updated_at"])

        return user, profile
