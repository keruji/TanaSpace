from django.urls import path

from . import views, property_views

app_name = "item_types"
urlpatterns = [
    path("<int:pk>/properties/new/", property_views.edit_property, name="property_create"),
    path("<int:pk>/properties/<uuid:property_id>/edit/", property_views.edit_property, name="property_edit"),
    path("<int:pk>/properties/<uuid:property_id>/archive/", property_views.archive_property, name="property_archive"),
    path("<int:pk>/properties/<uuid:property_id>/delete/", property_views.delete_property, name="property_delete"),
    path("<int:pk>/properties/<uuid:property_id>/reorder/", property_views.reorder_property, name="property_reorder"),
    path("", views.index, name="index"),
    path("new/", views.create, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/delete/", views.delete, name="delete"),
]
