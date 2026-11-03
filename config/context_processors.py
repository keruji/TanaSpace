from django.conf import settings


def app_css_version(request):
    """Refresh the browser's stylesheet when app.css changes."""
    stylesheet = settings.BASE_DIR / "static" / "css" / "app.css"
    return {"app_css_version": stylesheet.stat().st_mtime_ns}
