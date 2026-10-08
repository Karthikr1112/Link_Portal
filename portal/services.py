from django.utils import timezone
from .models import User


def check_and_deactivate_inactive_users():
    """
    Checks all active non-superuser accounts against their configured
    inactivity policy and deactivates any that have exceeded the threshold.
    Returns the count of newly deactivated users.
    """
    active_users = User.objects.filter(
        is_active=True,
        is_superuser=False,
    ).exclude(inactivity_policy=User.InactivityPolicy.NEVER)

    deactivated_count = 0
    for user in active_users:
        if user.is_inactive_due_to_policy():
            user.is_active = False
            user.save(update_fields=["is_active"])
            deactivated_count += 1

    return deactivated_count
