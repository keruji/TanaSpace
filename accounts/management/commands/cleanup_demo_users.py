from django.core.management.base import BaseCommand

from accounts.demo_cleanup import delete_expired_demos


class Command(BaseCommand):
    help = "Delete demo accounts and data older than the configured demo lifetime."

    def handle(self, *args, **options):
        count = delete_expired_demos()
        self.stdout.write(f"Deleted {count} expired demo account(s).")
