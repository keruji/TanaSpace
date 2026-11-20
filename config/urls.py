from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView
from accounts.urls import urlpatterns as account_routes, workspace_patterns
from items.urls import urlpatterns as item_routes
from items.views import favorites
from .views import health

account_patterns = [
    path("accounts/", include(account_routes)),
    path("tana/", include(workspace_patterns)),
]
item_patterns = [
    path("tana/items/", include(item_routes)),
    path("tana/favorites/", favorites, name="favorites"),
]

urlpatterns = [
    path("health/", health, name="health"),
    path("", TemplateView.as_view(template_name="landing.html"), name="landing"),
    path("", include((account_patterns, "accounts"))),
    path("", include((item_patterns, "items"))),
    path("tana", include("dashboard.urls")),
    path("tana/", RedirectView.as_view(pattern_name="dashboard:index")),
    path("tana/item_types/", include("item_types.urls")),
    path("admin/", admin.site.urls),
]
