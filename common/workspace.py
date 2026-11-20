"""Shared HTML responses for ordinary visits and enhanced workspace requests."""
from functools import wraps
from urllib.parse import urlencode, urlsplit

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import Resolver404, resolve
from django.utils.cache import add_never_cache_headers, patch_vary_headers


def is_partial(request):
    return request.headers.get("HX-Request") == "true"


def workspace_view(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = "/?" + urlencode({"next": request.get_full_path()})
            if is_partial(request) or request.headers.get("HX-History-Restore-Request"):
                response = HttpResponse(status=204)
                response["HX-Redirect"] = login_url
            else:
                response = redirect_to_login(request.get_full_path(), "/")
        else:
            response = view(request, *args, **kwargs)
        add_never_cache_headers(response)
        patch_vary_headers(response, ["HX-Request", "HX-Target", "HX-History-Restore-Request"])
        return response
    return wrapped


def return_url(request, fallback):
    """Only permit local, non-modal workspace destinations; never trust a header."""
    candidate = request.POST.get("return_to") or request.GET.get("return_to") or request.headers.get("X-Workspace-Return", "")
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return fallback
    if parsed.scheme or parsed.netloc or not candidate.startswith("/") or candidate.startswith("//") or "\\" in candidate:
        return fallback
    try:
        name = resolve(parsed.path).view_name
    except Resolver404:
        return fallback
    if name not in {"dashboard:index", "items:index", "items:favorites", "accounts:profile", "accounts:settings", "item_types:index"}:
        return fallback
    return parsed.path + ("?" + parsed.query if parsed.query else "")


def workspace_render(request, body_template, context, *, title, window_template=None):
    context = {
        **context, "body_template": body_template, "window_template": window_template,
        "page_title": title, "is_partial": is_partial(request),
    }
    target = request.headers.get("HX-Target")
    if is_partial(request) and target == "modal-host" and window_template:
        template = "app/window_response.html"
    elif is_partial(request) and target == "main":
        template = body_template
    elif is_partial(request):
        template = "app/workspace_response.html"
    else:
        template = "app/workspace_page.html"
    return render(request, template, context)


def mutation(response, kind, *, url=None, close=False):
    response["X-Workspace-Changed"] = kind
    if url:
        response["X-Workspace-URL"] = url
    if close:
        response["X-Workspace-Close"] = "true"
    return response
