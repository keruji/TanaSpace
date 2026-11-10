"""Remove demo accounts after their short, fixed lifetime."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone


def delete_expired_demos():
    cutoff = timezone.now() - timedelta(seconds=settings.DEMO_ACCOUNT_TTL_SECONDS)
    user_ids = list(
        get_user_model().objects.filter(is_demo=True, date_joined__lte=cutoff)
        .values_list("pk", flat=True)
    )
    if not user_ids:
        return 0
    expired_ids = {str(pk) for pk in user_ids}

    from items.models import Item

    with transaction.atomic():
        Item.objects.filter(owner_id__in=user_ids).delete()
        get_user_model().objects.filter(pk__in=user_ids, is_demo=True).delete()
        Session.objects.filter(expire_date__lte=timezone.now()).delete()
        for session in Session.objects.iterator(chunk_size=500):
            if session.get_decoded().get("_auth_user_id") in expired_ids:
                session.delete()
    return len(user_ids)
