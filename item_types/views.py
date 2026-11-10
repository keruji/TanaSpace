from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .forms import ItemTypeForm
from .models import ItemTypes


LIST_LIMIT = 40


def page(request, *, form=None, selected_type=None, modal_mode=None):
    item_types = ItemTypes.objects.filter(owner=request.user)
    page_obj = Paginator(item_types, LIST_LIMIT).get_page(request.GET.get("page"))
    return render(request, "item_types/index.html", {
        "active_nav": "item_types",
        "item_types": page_obj.object_list,
        "page_obj": page_obj,
        "type_count": page_obj.paginator.count,
        "at_type_limit": page_obj.paginator.count >= settings.MAX_ITEM_TYPES_PER_USER,
        "form": form,
        "selected_type": selected_type,
        "modal_mode": modal_mode,
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
    form = ItemTypeForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if ItemTypes.objects.filter(owner=request.user).count() < settings.MAX_ITEM_TYPES_PER_USER:
                item_type = form.save(commit=False)
                item_type.owner = request.user
                item_type.save()
                return redirect("item_types:detail", pk=item_type.pk)
        form.add_error(None, "You can save up to 20 types. Delete one before adding another.")
    return page(request, form=form, modal_mode="create")


@never_cache
@login_required
@require_http_methods(["GET"])
def detail(request, pk):
    item_type = get_object_or_404(ItemTypes, pk=pk, owner=request.user)
    return page(request, selected_type=item_type, modal_mode="detail")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def edit(request, pk):
    item_type = get_object_or_404(ItemTypes, pk=pk, owner=request.user)
    form = ItemTypeForm(request.POST if request.method == "POST" else None, instance=item_type)
    if request.method == "POST" and form.is_valid():
        item_type = form.save(commit=False)
        item_type.mark_edited(request.user)
        item_type.save()
        return redirect("item_types:detail", pk=item_type.pk)
    return page(request, form=form, selected_type=item_type, modal_mode="edit")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def delete(request, pk):
    item_type = get_object_or_404(ItemTypes, pk=pk, owner=request.user)
    if request.method == "POST":
        try:
            item_type.delete()
        except ProtectedError:
            messages.error(request, "This type is used by items. Move or delete those items first.")
            return redirect("item_types:detail", pk=pk)
        return redirect("item_types:index")
    return page(request, selected_type=item_type, modal_mode="delete")
