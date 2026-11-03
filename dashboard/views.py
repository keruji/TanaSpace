from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from items.models import Item


@never_cache
@login_required
def index(request):
    return render(request, "dashboard/index.html", {
        "active_nav": "dashboard",
        "recent_items": Item.objects.filter(owner=request.user)[:3],
    })
