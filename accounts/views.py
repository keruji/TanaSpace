from secrets import randbelow

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth.views import LogoutView
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.decorators.http import require_POST

from .demo_cleanup import delete_expired_demos
from .forms import SignUpForm


@require_POST
def start_demo(request):
    if request.user.is_authenticated:
        return redirect("dashboard:index")

    delete_expired_demos()
    if get_user_model().objects.filter(is_demo=True).count() >= settings.DEMO_MAX_ACTIVE_USERS:
        return HttpResponse("Demo spaces are temporarily full. Please try again later.", status=429)
    for _ in range(10):
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(
                    username=f"demo{randbelow(1_000_000_000):09d}",
                    is_demo=True,
                )
            break
        except IntegrityError:
            continue
    else:
        raise RuntimeError("Could not allocate a unique demo username.")
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(settings.DEMO_ACCOUNT_TTL_SECONDS)
    return redirect("dashboard:index")


class DemoLogoutView(LogoutView):
    def post(self, request, *args, **kwargs):
        demo_user = request.user if request.user.is_authenticated and request.user.is_demo else None
        response = super().post(request, *args, **kwargs)
        if demo_user is not None:
            from items.models import Item

            Item.objects.filter(owner=demo_user).delete()
            demo_user.delete()
        return response


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("dashboard:index")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard:index")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response
