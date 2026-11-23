"""Opt-in development demos. The cookie is a private, revocable bearer credential."""
from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe

from django.conf import settings
from django.utils import timezone

from .models import DevelopmentDemoAccess

COOKIE_NAME = "tanaspace_dev_demo"
COOKIE_PATH = "/accounts/demo/"
COOKIE_AGE = 30 * 24 * 60 * 60


def enabled():
    return settings.DEBUG and settings.DEV_DEMO_ENABLED


def eligible(user):
    return enabled() and user.is_authenticated and user.is_demo and user.is_development_demo and user.is_active


def resume_user(request):
    token = request.COOKIES.get(COOKIE_NAME, "")
    if not enabled() or not 32 <= len(token) <= 128:
        return None
    access = DevelopmentDemoAccess.objects.select_related("user").filter(
        token_hash=sha256(token.encode()).hexdigest(), expires_at__gt=timezone.now(),
        user__is_demo=True, user__is_development_demo=True, user__is_active=True,
    ).first()
    return access.user if access else None


def issue_cookie(response, user):
    token = token_urlsafe(32)
    DevelopmentDemoAccess.objects.update_or_create(user=user, defaults={
        "token_hash": sha256(token.encode()).hexdigest(),
        "expires_at": timezone.now() + timedelta(seconds=COOKIE_AGE),
    })
    response.set_cookie(COOKIE_NAME, token, max_age=COOKIE_AGE, httponly=True,
                        samesite="Strict", secure=not settings.DEBUG, path=COOKIE_PATH)
    return response
