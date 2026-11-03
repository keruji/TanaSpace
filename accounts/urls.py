from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from .views import SignUpView

app_name = "accounts"
urlpatterns = [
    path("login/", LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("signup/", SignUpView.as_view(), name="signup"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
