from django.conf import settings


def app_css_version(request):
    """Refresh the compiled stylesheet when any CSS source changes."""
    stylesheets = list((settings.BASE_DIR / "src" / "css").glob("*.css"))
    stylesheets.append(settings.BASE_DIR / "src" / "style.css")
    return {"app_css_version": max(path.stat().st_mtime_ns for path in stylesheets)}
