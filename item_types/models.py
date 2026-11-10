from django.db import models

from common.models import OwnershipModel


class ItemTypes(OwnershipModel):
    active = models.BooleanField(default=True)
    sequence = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["sequence", "-created_at", "-pk"]
