from django.urls import path
from django.views.generic import RedirectView

from .views import DemoLogoutView, start_demo

app_name = "accounts"
urlpatterns = [
    path("login/", RedirectView.as_view(pattern_name="landing"), name="login"),
    path("signup/", RedirectView.as_view(pattern_name="landing"), name="signup"),
    path("demo/", start_demo, name="demo"),
    path("logout/", DemoLogoutView.as_view(), name="logout"),
]
