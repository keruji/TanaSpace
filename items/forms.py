from django import forms

from .models import Item


class ItemForm(forms.ModelForm):
    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner is not None:
            self.fields["item_type"].queryset = self.fields["item_type"].queryset.filter(owner=owner)

    class Meta:
        model = Item
        fields = ["name", "item_type", "description", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Laptop, garden tools"}),
            "description": forms.Textarea(attrs={"placeholder": "What is this item? (optional)", "rows": 3}),
            "notes": forms.Textarea(attrs={"placeholder": "Any details to remember (optional)", "rows": 4}),
        }
