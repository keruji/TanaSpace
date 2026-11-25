import json
from functools import lru_cache

import markdown
from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET

from common.workspace import return_url, workspace_render, workspace_view
from .version import APP_VERSION

VISIBLE_LICENSES = frozenset({
    "TanaSpace", "OpenMoji", "Lucide", "Django", "htmx.org",
    "psycopg", "psycopg-binary", "gunicorn", "Markdown",
})


@lru_cache(maxsize=1)
def license_entries():
    base = settings.BASE_DIR
    entries = [
        {"name": "TanaSpace", "license": "PolyForm Noncommercial 1.0.0", "text": (base / "LICENSE").read_text()},
        {"name": "OpenMoji", "license": "CC BY-SA 4.0", "text": (base / "static/images/openmoji/LICENSE.txt").read_text(), "credit": "OpenMoji icons by the OpenMoji project. Black SVGs are used unmodified and displayed with a CSS mask."},
        {"name": "Lucide", "license": "ISC", "text": (base / "static/images/lucide-LICENSE.txt").read_text()},
    ]
    entries += json.loads((base / "common/dependency_licenses.json").read_text())
    # Only render Markdown from the bundled, trusted license files, never user input.
    for entry in entries:
        if entry["name"] == "TanaSpace" or entry["text"].startswith("LICENSE.md\n"):
            text = entry["text"].removeprefix("LICENSE.md\n")
            entry["rendered"] = mark_safe(markdown.markdown(text, extensions=["toc"]))
    return entries


def help_page(request, section):
    back = return_url(request, reverse("dashboard:index"))
    entries = license_entries() if section == "licenses" else []
    return workspace_render(request, "help/content.html", {
        "return_to": back, "page_url": reverse("dashboard:index"), "active_nav": "",
        "section": section, "app_version": APP_VERSION,
        "licenses": [entry for entry in entries if entry["name"] in VISIBLE_LICENSES],
        "additional_licenses": [entry for entry in entries if entry["name"] not in VISIBLE_LICENSES],
    }, title=("Licenses" if section == "licenses" else "About") + " · TanaSpace",
        window_template="help/window.html")


@workspace_view
@require_GET
def about(request):
    return help_page(request, "about")


@workspace_view
@require_GET
def licenses(request):
    return help_page(request, "licenses")
