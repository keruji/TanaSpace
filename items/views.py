from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .forms import ItemForm
from .models import Item
from item_types.models import ItemTypes


LIST_LIMIT = 40


def page(request, *, form=None, selected_item=None, modal_mode=None):
    items = Item.objects.filter(owner=request.user).select_related("item_type")
    page_obj = Paginator(items, LIST_LIMIT).get_page(request.GET.get("page"))
    return render(request, "items/index.html", {
        "active_nav": "items",
        "items": page_obj.object_list,
        "page_obj": page_obj,
        "item_count": page_obj.paginator.count,
        "at_item_limit": page_obj.paginator.count >= settings.MAX_ITEMS_PER_USER,
        "form": form,
        "selected_item": selected_item,
        "modal_mode": modal_mode,
        "needs_type": modal_mode == "create" and not ItemTypes.objects.filter(owner=request.user).exists(),
    })


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def index(request):
    if request.method == "POST":
        return create(request)
    return page(request)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def create(request):
    form = ItemForm(request.POST if request.method == "POST" else None, owner=request.user)
    if request.method == "POST" and ItemTypes.objects.filter(owner=request.user).exists() and form.is_valid():
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if Item.objects.filter(owner=request.user).count() < settings.MAX_ITEMS_PER_USER:
                item = form.save(commit=False)
                item.owner = request.user
                item.save()
                return redirect("items:detail", pk=item.pk)
        form.add_error(None, "You can save up to 100 items. Delete one before adding another.")
    return page(request, form=form, modal_mode="create")


@never_cache
@login_required
@require_http_methods(["GET"])
def detail(request, pk):
    item = get_object_or_404(Item.objects.select_related("item_type"), pk=pk, owner=request.user)
    return page(request, selected_item=item, modal_mode="detail")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def edit(request, pk):
    item = get_object_or_404(Item, pk=pk, owner=request.user)
    form = ItemForm(request.POST if request.method == "POST" else None, instance=item, owner=request.user)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.mark_edited(request.user)
        item.save()
        return redirect("items:detail", pk=item.pk)
    return page(request, form=form, selected_item=item, modal_mode="edit")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def delete(request, pk):
    item = get_object_or_404(Item, pk=pk, owner=request.user)
    if request.method == "POST":
        item.delete()
        return redirect("items:index")
    return page(request, selected_item=item, modal_mode="delete")
