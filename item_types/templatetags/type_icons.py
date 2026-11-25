from django import template
from django.templatetags.static import static
from item_types.icons import DEFAULT_ICON, ICON_IDS

register = template.Library()


@register.simple_tag
def type_icon_url(value):
    code = value if value in ICON_IDS else DEFAULT_ICON
    return static(f"images/openmoji/{code}.svg")
