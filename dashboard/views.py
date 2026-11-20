from django.db.models import Count, Q
from django.urls import reverse
from django.views.decorators.http import require_GET
from common.workspace import workspace_render, workspace_view
from items.models import Item
from item_types.models import ItemTypes


@workspace_view
@require_GET
def index(request):
    items = Item.objects.filter(owner=request.user)
    return workspace_render(request, "dashboard/content.html", {
        "active_nav": "dashboard", "page_url": reverse("dashboard:index"),
        "recent_items": items.select_related("item_type")[:3],
        "totals": items.aggregate(items=Count("pk"), favorites=Count("pk", filter=Q(is_favorite=True))),
        "type_total": ItemTypes.objects.filter(owner=request.user).count(),
    }, title="Dashboard · TanaSpace")
