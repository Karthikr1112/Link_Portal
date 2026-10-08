from django.core.management.base import BaseCommand
from portal.services import check_and_deactivate_inactive_users


class Command(BaseCommand):
    help = "Check and automatically deactivate users who have been inactive longer than their configured policy."

    def handle(self, *args, **options):
        count = check_and_deactivate_inactive_users()
        if count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully checked user accounts: {count} user(s) were deactivated due to inactivity."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Inactivity check complete: 0 users required deactivation."
                )
            )
