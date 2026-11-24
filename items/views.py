from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django import forms
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.db.models.fields.json import KeyTextTransform
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from common.workspace import is_partial, mutation, return_url, workspace_render, workspace_view
from item_types.models import ItemTypes
from .forms import ItemForm, ItemSearchForm
from .models import Item
from item_types.properties import detail_properties

LIST_LIMIT = 40


def page(request, *, form=None, selected_item=None, modal_mode=None, favorites_only=False):
    owned = Item.objects.filter(owner=request.user)
    search = ItemSearchForm(request.GET, owner=request.user)
    items = owned.select_related("item_type")
    if favorites_only:
        items = items.filter(is_favorite=True)
    if search.is_valid():
        if search.cleaned_data["q"]:
            items = items.filter(Q(name__icontains=search.cleaned_data["q"]) | Q(description__icontains=search.cleaned_data["q"]))
        if search.cleaned_data["type"]:
            items = items.filter(item_type=search.cleaned_data["type"])
        prop = search.cleaned_data["property"]
        if prop:
            items = items.filter(item_type_id=prop.item_type_id)
            if prop.data_type == "text":
                items = items.annotate(filter_property_text=KeyTextTransform(str(prop.pk), "property_values"))
                items = items.filter(filter_property_text__icontains=search.cleaned_data["filter_value"])
            elif prop.data_type == "dropdown":
                items = items.filter(**{f"property_values__{prop.pk}__in": search.cleaned_data["filter_value"]})
            else:
                items = items.filter(**{f"property_values__{prop.pk}": search.cleaned_data["filter_value"]})
    else:
        items = items.none()
    page_obj = Paginator(items, LIST_LIMIT).get_page(request.GET.get("page"))
    base = reverse("items:favorites" if favorites_only else "items:index")
    query = request.GET.copy()
    query.pop("return_to", None)
    query.pop("page", None)
    pagination_query = query.urlencode()
    page_url = base + ("?" + request.GET.urlencode() if request.GET and not modal_mode else "")
    back = return_url(request, base)
    title = "Favorites" if favorites_only else "My Tana"
    count = owned.count()
    context = {
        "active_nav": "favorites" if favorites_only else "items", "page_url": page_url,
        "items": page_obj.object_list, "page_obj": page_obj, "search_form": search,
        "item_count": count, "result_count": page_obj.paginator.count,
        "at_item_limit": count >= settings.MAX_ITEMS_PER_USER, "favorites_only": favorites_only,
        "property_rows": detail_properties(selected_item) if selected_item else ([], []),
        "form": form, "selected_item": selected_item, "modal_mode": modal_mode,
        "needs_type": modal_mode == "create" and not ItemTypes.objects.filter(owner=request.user).exists(),
        "return_to": back, "return_query": urlencode({"return_to": back}),
        "pagination_query": pagination_query, "list_title": title,
    }
    if modal_mode:
        title = {"create": "Add an item", "edit": "Edit item", "delete": "Delete item", "detail": selected_item.name if selected_item else "Item"}[modal_mode]
    return workspace_render(request, "items/content.html", context, title=title + " · TanaSpace",
                            window_template="items/window.html" if modal_mode else None)


@workspace_view
@require_http_methods(["GET", "POST"])
def index(request):
    return create(request) if request.method == "POST" else page(request)


@workspace_view
@require_http_methods(["GET"])
def favorites(request):
    return page(request, favorites_only=True)


def saved_response(request, item):
    if not is_partial(request):
        return redirect("items:detail", pk=item.pk)
    response = page(request, selected_item=item, modal_mode="detail")
    return mutation(response, "items", url=reverse("items:detail", args=[item.pk]))


@workspace_view
@require_http_methods(["GET", "POST"])
@transaction.atomic
def create(request):
    if request.method == "POST":
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
    loading = request.method == "POST" and request.POST.get("_action") == "load_properties"
    form = ItemForm(request.POST if request.method == "POST" else None, owner=request.user, loading=loading)
    if request.method == "POST" and not loading and ItemTypes.objects.filter(owner=request.user).exists() and form.is_valid():
        if Item.objects.filter(owner=request.user).count() < settings.MAX_ITEMS_PER_USER:
            item = form.save(commit=False)
            item.owner = request.user
            item.save()
            return saved_response(request, item)
        form.add_error(None, "You can save up to 100 items. Delete one before adding another.")
    return page(request, form=form, modal_mode="create")


@workspace_view
@require_http_methods(["GET"])
def detail(request, pk):
    item = get_object_or_404(Item.objects.select_related("item_type"), pk=pk, owner=request.user)
    return page(request, selected_item=item, modal_mode="detail")


@workspace_view
@require_http_methods(["GET", "POST"])
@transaction.atomic
def edit(request, pk):
    if request.method == "POST":
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
    item = get_object_or_404(Item, pk=pk, owner=request.user)
    loading = request.method == "POST" and request.POST.get("_action") == "load_properties"
    form = ItemForm(request.POST if request.method == "POST" else None, instance=item, owner=request.user, loading=loading)
    if request.method == "POST" and not loading and form.is_valid():
        item = form.save(commit=False)
        item.mark_edited(request.user)
        item.save()
        return saved_response(request, item)
    return page(request, form=form, selected_item=item, modal_mode="edit")


@workspace_view
@require_http_methods(["POST"])
def custom_fields(request):
    item = None
    if request.POST.get("_item_id"):
        try:
            item_id = forms.IntegerField(min_value=1).clean(request.POST["_item_id"])
        except ValidationError:
            return HttpResponseBadRequest("Choose a valid item.")
        item = get_object_or_404(Item, pk=item_id, owner=request.user)
    form = ItemForm(request.POST, instance=item, owner=request.user, loading=True)
    if request.POST.get("item_type") and not form.selected_type:
        return HttpResponseBadRequest("Choose a type owned by this user.")
    response = render(request, "items/custom_fields.html", {"form": form})
    from django.utils.cache import add_never_cache_headers
    add_never_cache_headers(response)
    return response


@workspace_view
@require_http_methods(["GET", "POST"])
@transaction.atomic
def delete(request, pk):
    if request.method == "POST":
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
    item = get_object_or_404(Item, pk=pk, owner=request.user)
    if request.method == "POST":
        item.delete()
        if is_partial(request):
            return mutation(HttpResponse(), "items", close=True)
        return redirect(return_url(request, reverse("items:index")))
    return page(request, selected_item=item, modal_mode="delete")


@workspace_view
@require_http_methods(["POST"])
@transaction.atomic
def favorite(request, pk):
    if request.method == "POST":
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
    item = get_object_or_404(Item, pk=pk, owner=request.user)
    desired = request.POST.get("favorite")
    if desired not in {"true", "false"}:
        return HttpResponseBadRequest("Choose a valid favorite state.")
    Item.objects.filter(pk=item.pk, owner=request.user).update(is_favorite=desired == "true")
    item.is_favorite = desired == "true"
    if is_partial(request):
        return mutation(page(request, selected_item=item, modal_mode="detail"), "items")
    return redirect(return_url(request, reverse("items:detail", args=[item.pk])))
