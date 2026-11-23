from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Start with standard username auth; extend here as account needs grow."""

    is_demo = models.BooleanField(default=False, editable=False)
    is_development_demo = models.BooleanField(default=False, db_default=False, editable=False)
    nickname = models.CharField(max_length=80, blank=True, default="", db_default="")

    @property
    def display_name(self):
        return self.nickname.strip() or " ".join(
            part.strip() for part in (self.first_name, self.last_name) if part.strip()
        ) or self.username


class DevelopmentDemoAccess(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="demo_access")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
