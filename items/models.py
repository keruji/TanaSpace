from django.core.exceptions import ValidationError
from django.db import models

from common.models import OwnershipModel


class Item(OwnershipModel):
    item_type = models.ForeignKey(
        "item_types.ItemTypes",
        on_delete=models.PROTECT,
        related_name="items",
    )
    description = models.CharField(max_length=500, blank=True)
    notes = models.CharField(max_length=2000, blank=True)

    def clean(self):
        super().clean()
        if self.owner_id and self.item_type_id and self.item_type.owner_id != self.owner_id:
            raise ValidationError({"item_type": "Choose a type owned by this user."})

    class Meta:
        ordering = ["-created_at", "-pk"]
