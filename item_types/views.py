from django.contrib import messages
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse
from django.urls import reverse
from django.db.models import Count, Q
from urllib.parse import urlencode
from common.workspace import is_partial, mutation, return_url, workspace_render, workspace_view
from django.views.decorators.http import require_http_methods

from .forms import ItemTypeForm
from .models import ItemTypes


LIST_LIMIT = 40


def page(request, *, form=None, selected_type=None, modal_mode=None):
    item_types = ItemTypes.objects.filter(owner=request.user).annotate(item_count=Count("items", filter=Q(items__owner=request.user))).order_by(*ItemTypes._meta.ordering)
    page_obj = Paginator(item_types, LIST_LIMIT).get_page(request.GET.get("page"))
    back = return_url(request, reverse("item_types:index"))
    title = {"create": "Add a type", "edit": "Edit type", "delete": "Delete type", "detail": selected_type.name if selected_type else "Tana Type"}.get(modal_mode, "Tana Types")
    return workspace_render(request, "item_types/content.html", {
        "active_nav": "settings", "page_url": reverse("item_types:index") + (("?" + request.GET.urlencode()) if request.GET and not modal_mode else ""),
        "return_to": back, "return_query": urlencode({"return_to": back}),
        "item_types": page_obj.object_list,
        "page_obj": page_obj,
        "type_count": page_obj.paginator.count,
        "at_type_limit": page_obj.paginator.count >= settings.MAX_ITEM_TYPES_PER_USER,
        "properties": selected_type.properties.filter(archived_at__isnull=True) if selected_type else [],
        "archived_properties": selected_type.properties.filter(archived_at__isnull=False) if selected_type else [],
        "incomplete_items": incomplete_count(selected_type) if selected_type else 0,
        "form": form,
        "selected_type": selected_type,
        "modal_mode": modal_mode,
    }, title=title + " · TanaSpace", window_template="item_types/window.html" if modal_mode else None)


@workspace_view
@require_http_methods(["GET", "POST"])
def index(request):
    if request.method == "POST":
        return create(request)
    return page(request)


@workspace_view
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
                return saved_response(request, item_type)
        form.add_error(None, "You can save up to 20 types. Delete one before adding another.")
    return page(request, form=form, modal_mode="create")


@workspace_view
@require_http_methods(["GET"])
def detail(request, pk):
    item_type = get_object_or_404(ItemTypes, pk=pk, owner=request.user)
    return page(request, selected_type=item_type, modal_mode="detail")


@workspace_view
@require_http_methods(["GET", "POST"])
@transaction.atomic
def edit(request, pk):
    if request.method == "POST":
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
    item_type = get_object_or_404(ItemTypes, pk=pk, owner=request.user)
    form = ItemTypeForm(request.POST if request.method == "POST" else None, instance=item_type)
    if request.method == "POST" and form.is_valid():
        item_type = form.save(commit=False)
        item_type.mark_edited(request.user)
        item_type.save()
        return saved_response(request, item_type)
    return page(request, form=form, selected_type=item_type, modal_mode="edit")


@workspace_view
@require_http_methods(["GET", "POST"])
@transaction.atomic
def delete(request, pk):
    if request.method == "POST":
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
    item_type = get_object_or_404(ItemTypes, pk=pk, owner=request.user)
    if request.method == "POST":
        try:
            item_type.delete()
        except ProtectedError:
            messages.error(request, "This type is used by items. Move or delete those items first.")
            if is_partial(request):
                return page(request, selected_type=item_type, modal_mode="delete")
            return redirect("item_types:detail", pk=pk)
        if is_partial(request):
            return mutation(HttpResponse(), "types", close=True)
        return redirect(return_url(request, reverse("item_types:index")))
    return page(request, selected_type=item_type, modal_mode="delete")


def saved_response(request, item_type):
    if not is_partial(request):
        return redirect("item_types:detail", pk=item_type.pk)
    return mutation(page(request, selected_type=item_type, modal_mode="detail"), "types",
                    url=reverse("item_types:detail", args=[item_type.pk]))


def incomplete_count(item_type):
    required = [str(prop.pk) for prop in item_type.properties.filter(required=True, archived_at__isnull=True)]
    return sum(any(item.property_values.get(key) is None or item.property_values.get(key) == "" for key in required)
               for item in item_type.items.only("property_values")) if required else 0
