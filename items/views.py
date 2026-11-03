from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .forms import ItemForm
from .models import Item


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def index(request):
    form = ItemForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.owner = request.user
        item.save()
        return redirect("items:index")

    return render(request, "items/index.html", {
        "active_nav": "items",
        "form": form,
        "items": Item.objects.filter(owner=request.user),
    })


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def edit(request, pk):
    item = get_object_or_404(Item, pk=pk, owner=request.user)
    form = ItemForm(request.POST if request.method == "POST" else None, instance=item)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.mark_edited(request.user)
        item.save()
        return redirect("items:index")

    return render(request, "items/edit.html", {
        "active_nav": "items",
        "form": form,
        "item": item,
    })
