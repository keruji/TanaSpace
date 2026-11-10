from django.conf import settings
from django.db import models
from django.utils import timezone


class OwnershipModel(models.Model):

    name = models.CharField(max_length=160)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_owned",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="%(app_label)s_%(class)s_edited",
    )
    edited_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    def mark_edited(self, user):
        """Record the editor just before saving an existing record."""
        self.edited_at = timezone.now()
        self.edited_by = user
