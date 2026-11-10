from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Start with standard username auth; extend here as account needs grow."""

    is_demo = models.BooleanField(default=False, editable=False)

    @property
    def display_name(self):
        return self.username
