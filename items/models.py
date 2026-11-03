from django.conf import settings
from django.db import models
from django.utils import timezone


class Item(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="items"
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True, editable=False)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="edited_items",
    )

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return self.name

    def mark_edited(self, user):
        """Record the editor just before saving an existing item."""
        self.edited_at = timezone.now()
        self.edited_by = user
