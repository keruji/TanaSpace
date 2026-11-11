from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView
from .views import health

urlpatterns = [
    path("health/", health, name="health"),
    path("", TemplateView.as_view(template_name="landing.html"), name="landing"),
    path("accounts/", include("accounts.urls")),
    path("tana", include("dashboard.urls")),
    path("tana/", RedirectView.as_view(pattern_name="dashboard:index")),
    path("tana/items/", include("items.urls")),
    path("tana/item_types/", include("item_types.urls")),
    path("admin/", admin.site.urls),
]
