from django import forms

from .models import Item
from item_types.models import ItemTypes


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


class ItemSearchForm(forms.Form):
    q = forms.CharField(max_length=160, required=False, label="Search items")
    type = forms.ModelChoiceField(queryset=ItemTypes.objects.none(), required=False, label="Tana Type", empty_label="All types")

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].queryset = ItemTypes.objects.filter(owner=owner)
