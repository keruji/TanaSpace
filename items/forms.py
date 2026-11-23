from django import forms
from django.forms.utils import ErrorDict

from .models import Item
from item_types.properties import property_field, serialize_value, has_value
from item_types.models import ItemTypes


class ItemForm(forms.ModelForm):
    schema_version = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, owner=None, loading=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_type_id = self.instance.item_type_id
        self.saved_values = dict(self.instance.property_values or {})
        self.fields["item_type"].queryset = ItemTypes.objects.filter(owner=owner) if owner else ItemTypes.objects.none()
        selected = self.data.get("item_type") if self.is_bound else self.original_type_id
        try:
            self.selected_type = self.fields["item_type"].queryset.filter(pk=selected).first() if selected else None
        except (ValueError, TypeError):
            self.selected_type = None
        self.definitions = list(self.selected_type.properties.filter(archived_at__isnull=True)) if self.selected_type else []
        current_version = self.selected_type.property_schema_version if self.selected_type else 0
        self.submitted_schema = self.data.get("schema_version") if self.is_bound else None
        if self.is_bound:
            data = self.data.copy()
            if loading and data.get("_loaded_type") != str(selected):
                for key in list(data):
                    if key.startswith("property_") or key == "confirm_type_change":
                        del data[key]
                if str(selected) == str(self.original_type_id):
                    for prop in self.definitions:
                        key = str(prop.pk)
                        if key in self.saved_values:
                            data["property_" + key] = initial_value(prop, self.saved_values[key])
            if loading:
                allowed = {"property_" + str(prop.pk) for prop in self.definitions}
                for key in list(data):
                    if key.startswith("property_") and key not in allowed:
                        del data[key]
            data["schema_version"] = str(current_version)
            self.data = data
        self.initial["schema_version"] = current_version
        for prop in self.definitions:
            key = str(prop.pk)
            saved = self.saved_values.get(key) if self.selected_type.pk == self.original_type_id else None
            self.fields["property_" + key] = property_field(prop, saved)
            self.initial["property_" + key] = initial_value(prop, saved)
        self.type_change_has_values = bool(self.selected_type and self.original_type_id and self.selected_type.pk != self.original_type_id and any(has_value(v) for v in self.saved_values.values()))
        if self.type_change_has_values:
            self.fields["confirm_type_change"] = forms.BooleanField(
                label="Clear the previous type's custom values, including archived values", required=True)

        if loading:
            self._errors = ErrorDict()

    @property
    def core_fields(self):
        return [self[name] for name in self.Meta.fields]

    @property
    def custom_fields(self):
        return [self["property_" + str(prop.pk)] for prop in self.definitions]

    def clean(self):
        data = super().clean()
        allowed = {"property_" + str(prop.pk) for prop in self.definitions}
        if any(key.startswith("property_") and key not in allowed for key in self.data):
            self.add_error(None, "An unknown or unavailable custom property was submitted. Reload the properties.")
        if self.selected_type and (self.submitted_schema != str(self.selected_type.property_schema_version)):
            # Old forms without custom definitions remain compatible with the original interface.
            if self.selected_type.property_schema_version or self.definitions or self.submitted_schema not in (None, "0"):
                self.add_error(None, "Properties changed or have not loaded. Load properties, review the values, and save again.")
        return data

    def save(self, commit=True):
        item = super().save(commit=False)
        values = dict(self.saved_values) if item.item_type_id == self.original_type_id else {}
        for prop in self.definitions:
            key = str(prop.pk)
            value = self.cleaned_data["property_" + key]
            if value is None or value == "":
                values.pop(key, None)
            else:
                values[key] = serialize_value(value)
        item.property_values = values
        if commit:
            item.save()
        return item

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


def initial_value(prop, value):
    if prop.data_type == "boolean" and prop.required and value is not None:
        return "true" if value else "false"
    return value
