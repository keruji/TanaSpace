"""Definition-aware form fields, safe configuration, and display formatting."""
from datetime import date
from decimal import Decimal
import uuid

from django import forms
from django.core.exceptions import ValidationError

MAX_ACTIVE_PROPERTIES = 20
MAX_PROPERTIES = 50
MAX_OPTIONS = 50
NUMBER_LIMITS = {"max_digits": 12, "decimal_places": 4}


def has_value(value):
    return value is not None and value != ""


def number_field(**kwargs):
    return forms.DecimalField(**NUMBER_LIMITS, **kwargs)


def property_field(prop, saved=None):
    common = {"label": prop.name, "required": prop.required}
    config = prop.configuration
    if prop.data_type == "text":
        return forms.CharField(max_length=1000, **common)
    if prop.data_type == "number":
        return number_field(min_value=Decimal(str(config["min"])) if "min" in config else None,
                            max_value=Decimal(str(config["max"])) if "max" in config else None, **common)
    if prop.data_type == "date":
        return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), input_formats=["%Y-%m-%d"], **common)
    if prop.data_type == "boolean":
        if prop.required:
            return forms.TypedChoiceField(choices=[("", "Choose Yes or No"), ("true", "Yes"), ("false", "No")],
                                          coerce=lambda value: value == "true", **common)
        return forms.BooleanField(**common)
    choices = [("", "Choose an option")]
    choices += [(option["id"], option["label"] + (" (archived)" if option.get("archived") else ""))
                for option in config.get("options", [])
                if not option.get("archived") or option["id"] == saved]
    return forms.ChoiceField(choices=choices, **common)


def serialize_value(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def formatted_value(prop, value):
    if not has_value(value):
        return "—"
    if prop.data_type == "boolean":
        return "Yes" if value else "No"
    if prop.data_type == "dropdown":
        return next((option["label"] for option in prop.configuration.get("options", []) if option["id"] == value), "—")
    if prop.data_type == "date":
        from django.utils.formats import date_format
        return date_format(date.fromisoformat(value), "M j, Y")
    return str(value)


def detail_properties(item):
    rows = [dict(property=prop, value=formatted_value(prop, item.property_values.get(str(prop.pk))))
            for prop in item.item_type.properties.all()]
    return ([row for row in rows if not row["property"].archived_at],
            [row for row in rows if row["property"].archived_at and has_value(item.property_values.get(str(row["property"].pk)))])


class OptionForm(forms.Form):
    id = forms.CharField(required=False, widget=forms.HiddenInput)
    label = forms.CharField(max_length=80, required=False)
    archived = forms.BooleanField(required=False, label="Archive option")


OptionFormSet = forms.formset_factory(OptionForm, extra=1, max_num=MAX_OPTIONS, validate_max=True, absolute_max=MAX_OPTIONS)


class PropertyForm(forms.Form):
    name = forms.CharField(max_length=80)
    data_type = forms.ChoiceField(choices=[("text", "Text"), ("number", "Number"), ("date", "Date"), ("boolean", "Boolean"), ("dropdown", "Dropdown")])
    required = forms.BooleanField(required=False)
    minimum = number_field(required=False, label="Minimum (numbers only)")
    maximum = number_field(required=False, label="Maximum (numbers only)")

    def __init__(self, *args, item_type, instance=None, **kwargs):
        self.item_type, self.instance = item_type, instance
        config = instance.configuration if instance else {}
        initial = {"name": instance.name, "data_type": instance.data_type, "required": instance.required,
                   "minimum": config.get("min"), "maximum": config.get("max")} if instance else {}
        super().__init__(*args, initial=initial, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        matches = self.item_type.properties.filter(archived_at__isnull=True, name__iexact=name)
        if self.instance:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise ValidationError("An active property already uses this name.")
        return name

    def clean(self):
        data = super().clean()
        minimum, maximum = data.get("minimum"), data.get("maximum")
        if data.get("data_type") == "number" and minimum is not None and maximum is not None and minimum > maximum:
            self.add_error("maximum", "Maximum must be at least the minimum.")
        return data

    def configuration(self, options):
        """Validate option identifiers against the stored definition, never client authority."""
        kind = self.cleaned_data["data_type"]
        if kind == "number":
            return {key: serialize_value(self.cleaned_data[field]) for key, field in [("min", "minimum"), ("max", "maximum")]
                    if self.cleaned_data.get(field) is not None}
        if kind != "dropdown":
            return {}
        old = {option["id"]: option for option in (self.instance.configuration.get("options", []) if self.instance else [])}
        seen, labels, result = set(), set(), []
        for entry in options.cleaned_data:
            identifier, label = entry.get("id", ""), entry.get("label", "").strip()
            if not identifier and not label:
                continue
            if identifier and (identifier not in old or identifier in seen):
                raise ValidationError("An option identifier is invalid or duplicated.")
            if not label:
                raise ValidationError("Existing options need a label. Archive them to remove them from new selections.")
            archived = bool(entry.get("archived")) or bool(old.get(identifier, {}).get("archived"))
            if not archived and label.casefold() in labels:
                raise ValidationError("Active option labels must be unique.")
            if not archived:
                labels.add(label.casefold())
            identifier = identifier or str(uuid.uuid4())
            seen.add(identifier)
            result.append({"id": identifier, "label": label, "archived": archived})
        if not old.keys() <= seen:
            raise ValidationError("Saved options cannot be deleted. Archive them instead.")
        if not any(not option["archived"] for option in result):
            raise ValidationError("Add at least one active dropdown option.")
        return {"options": result}
