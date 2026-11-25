"""URL-backed item search with shared custom properties."""
from functools import reduce
from operator import or_

from django import forms
from django.db.models import Q

from item_types.models import ItemTypes, ItemTypeProperty
from item_types.properties import property_field, serialize_value


def search_items(request, items):
    data = request.GET.copy()
    field, value = data.get('field', ''), data.get('value', '').strip()
    if value and (field in {'name', 'description', 'types'} or field.startswith('prop_')):
        data.appendlist(field, value)
    types = list(ItemTypes.objects.filter(owner=request.user).order_by('pk'))
    properties = list(ItemTypeProperty.objects.filter(item_type__owner=request.user, archived_at__isnull=True)
                      .order_by('item_type_id', 'sequence', 'pk'))
    type_map = {str(kind.pk): kind for kind in types}
    selected = data.getlist('types')
    errors = []
    if len(selected) > 20 or any(value not in type_map for value in selected):
        errors.append('Choose valid Tana Types.')
        selected = []
    selected = list(dict.fromkeys(selected))
    property_keys = [key for key in data if key.startswith('prop_')]
    if sum(len(data.getlist(key)) for key in property_keys) > 100:
        errors.append('Use at most 100 custom property values.')
        property_keys = []
    selected_set = {int(value) for value in selected}
    groups = {}
    for prop in properties:
        if prop.item_type_id in selected_set:
            groups.setdefault((prop.name.casefold(), prop.data_type), {})[prop.item_type_id] = prop
    shared = {str(next(iter(group.values())).pk): list(group.values()) for group in groups.values()
              if selected_set and set(group) == selected_set}
    metadata = [{'id': str(kind.pk), 'name': kind.name, 'properties': [
        {'id': str(prop.pk), 'name': prop.name, 'kind': prop.data_type,
         'options': [{'id': option['id'], 'label': option['label']} for option in prop.configuration.get('options', [])
                     if not option.get('archived')]}
        for prop in properties if prop.item_type_id == kind.pk]} for kind in types]
    chips = []
    for field, label in [('name', 'Name'), ('description', 'Description')]:
        values = data.getlist(field)
        if len(values) > 50 or any(len(value) > 160 for value in values):
            errors.append(f'{label} searches are too long.')
            continue
        values = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if values:
            items = items.filter(reduce(or_, [Q(**{f'{field}__icontains': value}) for value in values]))
        chips.extend({'key': field, 'value': value, 'label': f'{label}: {value}'} for value in values)
    if selected:
        items = items.filter(item_type_id__in=selected)
    chips.extend({'key': 'types', 'value': value, 'label': f'Tana Type: {type_map[value].name}'} for value in selected)
    date_field = forms.DateField(required=False, input_formats=['%Y-%m-%d'])
    dates = {}
    for key, label in [('created_from', 'From'), ('created_to', 'To')]:
        try:
            dates[key] = date_field.clean(data.get(key))
            if dates[key]:
                items = items.filter(**{f'created_at__date__{"gte" if key == "created_from" else "lte"}': dates[key]})
                chips.append({'key': key, 'value': dates[key].isoformat(), 'label': f'{label}: {dates[key]}'})
        except forms.ValidationError:
            errors.append('Enter valid creation dates.')
    if dates.get('created_from') and dates.get('created_to') and dates['created_from'] > dates['created_to']:
        errors.append('The start date must be before the end date.')
    for key in property_keys:
        source = next((prop for prop in properties if str(prop.pk) == key[5:]), None)
        group_map = groups.get((source.name.casefold(), source.data_type), {}) if source else {}
        group = list(group_map.values()) if selected_set and set(group_map) == selected_set else None
        values = list(dict.fromkeys(value.strip() for value in data.getlist(key) if value.strip()))
        if not group or len(values) > 50 or any(len(value) > 1000 for value in values):
            errors.append('Choose a valid shared property and value.')
            continue
        conditions = []
        for value in values:
            per_value = []
            for prop in group:
                try:
                    if prop.data_type == 'boolean':
                        choices = {'yes': True, 'true': True, 'no': False, 'false': False}
                        if value.casefold() not in choices:
                            raise forms.ValidationError('Choose Yes or No.')
                        parsed = choices[value.casefold()]
                    elif prop.data_type == 'dropdown':
                        options = [option['id'] for option in prop.configuration.get('options', [])
                                   if not option.get('archived') and option['label'].casefold() == value.casefold()]
                        if not options:
                            raise forms.ValidationError('Choose a shared dropdown option.')
                        parsed = options
                    else:
                        field = property_field(prop)
                        field.required = True
                        parsed = serialize_value(field.clean(value))
                    if prop.data_type == 'text':
                        condition = Q(**{f'property_values__{prop.pk}__icontains': parsed})
                    elif prop.data_type == 'dropdown':
                        condition = Q(**{f'property_values__{prop.pk}__in': parsed})
                    else:
                        condition = Q(**{f'property_values__{prop.pk}': parsed})
                    per_value.append(Q(item_type_id=prop.item_type_id) & condition)
                except forms.ValidationError:
                    errors.append(f'Enter a valid value for {prop.name}.')
            if len(per_value) == len(group):
                conditions.extend(per_value)
                chips.append({'key': 'prop_' + str(group[0].pk), 'value': value, 'label': f'{group[0].name}: {value}'})
        if conditions:
            items = items.filter(reduce(or_, conditions))
    if errors:
        items = items.none()
    available = [{'id': key, 'name': group[0].name} for key, group in shared.items()]
    return items, {'types': metadata, 'selected_types': selected, 'chips': chips, 'errors': errors, 'shared': available}
