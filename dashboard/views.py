from django.urls import reverse
from django.views.decorators.http import require_GET
from common.workspace import workspace_render, workspace_view
from items.models import Item


@workspace_view
@require_GET
def index(request):
    items = Item.objects.filter(owner=request.user)
    return workspace_render(request, "dashboard/content.html", {
        "active_nav": "dashboard", "page_url": reverse("dashboard:index"),
        "recent_items": items.select_related("item_type")[:3],
    }, title="Dashboard · TanaSpace")
