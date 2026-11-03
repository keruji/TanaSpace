from django import forms

from .models import Item


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ["name", "description", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Laptop, garden tools"}),
            "description": forms.Textarea(attrs={"placeholder": "What is this item? (optional)", "rows": 3}),
            "notes": forms.Textarea(attrs={"placeholder": "Any details to remember (optional)", "rows": 4}),
        }
