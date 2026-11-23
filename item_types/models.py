from django.db import models
from django.db.models.functions import Lower
import uuid

from common.models import OwnershipModel


class ItemTypes(OwnershipModel):
    property_schema_version = models.PositiveIntegerField(default=0, db_default=0)
    active = models.BooleanField(default=True)
    sequence = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["sequence", "-created_at", "-pk"]


class ItemTypeProperty(models.Model):
    class DataType(models.TextChoices):
        TEXT = "text", "Text"
        NUMBER = "number", "Number"
        DATE = "date", "Date"
        BOOLEAN = "boolean", "Boolean"
        DROPDOWN = "dropdown", "Dropdown"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item_type = models.ForeignKey(ItemTypes, on_delete=models.CASCADE, related_name="properties")
    name = models.CharField(max_length=80)
    data_type = models.CharField(max_length=12, choices=DataType.choices)
    required = models.BooleanField(default=False)
    sequence = models.PositiveIntegerField(default=0)
    configuration = models.JSONField(default=dict)
    archived_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["sequence", "pk"]
        constraints = [models.UniqueConstraint(
            Lower("name"), "item_type", condition=models.Q(archived_at__isnull=True),
            name="unique_active_property_name",
        )]
