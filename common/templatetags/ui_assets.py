"""Version shared assets even inside template includes using `only`."""
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def versioned_static(path):
    url = static(path)
    source = finders.find(path)
    if not source:
        return url
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.append(("v", str(Path(source).stat().st_mtime_ns)))
    return urlunsplit(parts._replace(query=urlencode(query)))
