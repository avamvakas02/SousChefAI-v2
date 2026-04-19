from django import forms

from .models import PantryItem


class PantryItemForm(forms.ModelForm):
    class Meta:
        model = PantryItem
        fields = ("name", "category", "quantity", "notes")
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ingredient name",
                    "autocomplete": "off",
                }
            ),
            "category": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Amount (optional)",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Notes (optional)",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            if not str(self.initial.get("quantity", "") or "").strip():
                self.initial["quantity"] = "1"
