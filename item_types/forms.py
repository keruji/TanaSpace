from django import forms

from .models import ItemTypes


class ItemTypeForm(forms.ModelForm):
    class Meta:
        model = ItemTypes
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Consumable, tool, component, etc."}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }
