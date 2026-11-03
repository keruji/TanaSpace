from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Start with standard username auth; extend here as account needs grow."""
