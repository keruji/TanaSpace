from django import forms

from .models import ItemTypes
from .icons import DEFAULT_ICON


class ItemTypeForm(forms.ModelForm):
    icon = forms.ChoiceField(choices=ItemTypes._meta.get_field('icon').choices, required=False, initial=DEFAULT_ICON, widget=forms.RadioSelect)

    def clean_icon(self):
        return self.cleaned_data.get('icon') or DEFAULT_ICON

    class Meta:
        model = ItemTypes
        fields = ["icon", "name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Consumable, tool, component, etc."}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }
