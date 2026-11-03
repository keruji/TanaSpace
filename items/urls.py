from django.urls import path

from . import views

app_name = "items"
urlpatterns = [
    path("", views.index, name="index"),
    path("<int:pk>/edit/", views.edit, name="edit"),
]
