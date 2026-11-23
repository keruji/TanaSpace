from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.http import HttpResponseBadRequest
from django.forms.utils import ErrorDict
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from common.workspace import workspace_view, workspace_render, return_url, is_partial, mutation
from .models import ItemTypes, ItemTypeProperty
from .properties import PropertyForm, OptionFormSet, MAX_ACTIVE_PROPERTIES, MAX_PROPERTIES, has_value, property_field


def editor_response(request, item_type):
    from .views import page
    from .forms import ItemTypeForm
    url = reverse("item_types:edit", args=[item_type.pk])
    if not is_partial(request):
        return redirect(url)
    return mutation(page(request, selected_type=item_type, form=ItemTypeForm(instance=item_type), modal_mode="edit"), "types", url=url)


def property_page(request, item_type, *, prop=None, form=None, options=None, archive=False, error=None):
    from urllib.parse import urlencode
    back = return_url(request, reverse("item_types:index"))
    return workspace_render(request, "item_types/content.html", {
        "active_nav": "settings", "page_url": reverse("item_types:index"),
        "selected_type": item_type, "property": prop, "form": form, "options": options,
        "archive_property": archive, "property_error": error,
        "item_types": ItemTypes.objects.filter(owner=request.user),
        "return_to": back, "return_query": urlencode({"return_to": back}),
    }, title="Custom property · TanaSpace", window_template="item_types/property_window.html")


def schema_matches(request, item_type):
    return request.POST.get("schema_version") == str(item_type.property_schema_version)


@workspace_view
@require_http_methods(["GET", "POST"])
@transaction.atomic
def edit_property(request, pk, property_id=None):
    if request.method == "POST":
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
    item_type = get_object_or_404(ItemTypes, pk=pk, owner=request.user)
    prop = get_object_or_404(item_type.properties, pk=property_id, archived_at__isnull=True) if property_id else None
    data = request.POST.copy() if request.method == "POST" else None
    adding_option = data is not None and data.get("_action") == "add_option"
    if adding_option:
        try:
            count = int(data.get("options-TOTAL_FORMS", 0))
            if 0 <= count < 50:
                data["options-TOTAL_FORMS"] = str(count + 1)
        except (ValueError, TypeError):
            pass
    form = PropertyForm(data, item_type=item_type, instance=prop)
    options = OptionFormSet(data, prefix="options", initial=prop.configuration.get("options", []) if prop else [])
    if request.method == "POST" and not adding_option:
        valid = form.is_valid()
        option_valid = options.is_valid() if form.cleaned_data.get("data_type") == "dropdown" else True
        if not schema_matches(request, item_type):
            form.add_error(None, "Properties changed in another window. Review this form and save again.")
            valid = False
        if prop is None and (item_type.properties.count() >= MAX_PROPERTIES or item_type.properties.filter(archived_at__isnull=True).count() >= MAX_ACTIVE_PROPERTIES):
            form.add_error(None, "A type supports 20 active properties and 50 total including archived properties.")
            valid = False
        if valid and option_valid:
            try:
                config = form.configuration(options)
                candidate = ItemTypeProperty(item_type=item_type, name=form.cleaned_data["name"],
                    data_type=form.cleaned_data["data_type"], required=form.cleaned_data["required"], configuration=config)
                if prop:
                    saved = [item.property_values[str(prop.pk)] for item in item_type.items.only("property_values")
                             if has_value(item.property_values.get(str(prop.pk)))]
                    if prop.data_type != candidate.data_type and saved:
                        raise ValidationError("The data type cannot change while this property has saved values.")
                    if candidate.data_type == "number":
                        for value in saved:
                            property_field(candidate).clean(value)
                else:
                    candidate.sequence = max((p.sequence for p in item_type.properties.all()), default=-1) + 1
                if prop:
                    for field in ["name", "data_type", "required", "configuration"]:
                        setattr(prop, field, getattr(candidate, field))
                    prop.save()
                else:
                    candidate.save()
                ItemTypes.objects.filter(pk=item_type.pk).update(property_schema_version=F("property_schema_version") + 1)
                item_type.refresh_from_db()
                return editor_response(request, item_type)
            except ValidationError as exc:
                form.add_error(None, exc)
    if adding_option:
        form._errors = ErrorDict()
    response = property_page(request, item_type, prop=prop, form=form, options=options)
    if adding_option:
        response["X-Workspace-Form-Updated"] = "true"
    return response


@workspace_view
@require_http_methods(["GET", "POST"])
@transaction.atomic
def archive_property(request, pk, property_id):
    if request.method == "POST":
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
    item_type = get_object_or_404(ItemTypes, pk=pk, owner=request.user)
    prop = get_object_or_404(item_type.properties, pk=property_id, archived_at__isnull=True)
    error = None
    if request.method == "POST":
        if not schema_matches(request, item_type):
            error = "Properties changed. Review the confirmation and try again."
        elif request.POST.get("confirm_archive") != "yes":
            error = "Confirm that this property should be archived."
        else:
            prop.archived_at = timezone.now()
            prop.save(update_fields=["archived_at"])
            item_type.property_schema_version += 1
            item_type.save(update_fields=["property_schema_version"])
            return editor_response(request, item_type)
    return property_page(request, item_type, prop=prop, archive=True, error=error)


@workspace_view
@require_POST
@transaction.atomic
def reorder_property(request, pk, property_id):
    get_user_model().objects.select_for_update().get(pk=request.user.pk)
    item_type = get_object_or_404(ItemTypes, pk=pk, owner=request.user)
    prop = get_object_or_404(item_type.properties, pk=property_id, archived_at__isnull=True)
    if request.POST.get("direction") not in {"up", "down"} or not schema_matches(request, item_type):
        return HttpResponseBadRequest("The property order changed. Reload the editor and try again.")
    properties = list(item_type.properties.filter(archived_at__isnull=True))
    index = properties.index(prop)
    destination = index + (-1 if request.POST["direction"] == "up" else 1)
    if 0 <= destination < len(properties):
        properties[index], properties[destination] = properties[destination], properties[index]
        for sequence, entry in enumerate(properties):
            entry.sequence = sequence
        ItemTypeProperty.objects.bulk_update(properties, ["sequence"])
        item_type.property_schema_version += 1
        item_type.save(update_fields=["property_schema_version"])
    return editor_response(request, item_type)
