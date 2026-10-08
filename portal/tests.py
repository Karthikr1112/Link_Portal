from datetime import timedelta
from django.test import TestCase, RequestFactory
from django.utils import timezone

from portal.models import User
from portal.services import check_and_deactivate_inactive_users
from portal.forms import PortalAuthenticationForm


class UserInactivityPolicyTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123",
            is_active=True,
            inactivity_policy=User.InactivityPolicy.NEVER,
        )

    def test_default_never_policy_never_deactivates(self):
        # Set last login to 30 days ago
        self.user.last_login = self.now - timedelta(days=30)
        self.user.save()

        self.assertFalse(self.user.is_inactive_due_to_policy())
        deactivated = check_and_deactivate_inactive_users()
        self.assertEqual(deactivated, 0)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_one_week_policy_deactivates_after_7_days(self):
        self.user.inactivity_policy = User.InactivityPolicy.ONE_WEEK
        # Active within 5 days
        self.user.last_login = self.now - timedelta(days=5)
        self.user.save()
        self.assertFalse(self.user.is_inactive_due_to_policy())

        # Inactive for 8 days
        self.user.last_login = self.now - timedelta(days=8)
        self.user.save()
        self.assertTrue(self.user.is_inactive_due_to_policy())

        deactivated = check_and_deactivate_inactive_users()
        self.assertEqual(deactivated, 1)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_ten_days_policy_deactivates_after_10_days(self):
        self.user.inactivity_policy = User.InactivityPolicy.TEN_DAYS
        # Inactive for 8 days (safe under 10-day policy)
        self.user.last_login = self.now - timedelta(days=8)
        self.user.save()
        self.assertFalse(self.user.is_inactive_due_to_policy())

        # Inactive for 11 days (exceeds 10-day policy)
        self.user.last_login = self.now - timedelta(days=11)
        self.user.save()
        self.assertTrue(self.user.is_inactive_due_to_policy())

        deactivated = check_and_deactivate_inactive_users()
        self.assertEqual(deactivated, 1)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_manual_activation_resets_inactivity_timer(self):
        self.user.inactivity_policy = User.InactivityPolicy.ONE_WEEK
        self.user.last_login = self.now - timedelta(days=10)
        self.user.is_active = False
        self.user.save()

        # Admin manually activates account
        self.user.is_active = True
        self.user.save()

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertIsNotNone(self.user.last_activated_at)
        # Should now be 0 days inactive based on activation timestamp
        self.assertEqual(self.user.days_inactive, 0)
        self.assertFalse(self.user.is_inactive_due_to_policy())

    def test_superuser_is_never_deactivated(self):
        superuser = User.objects.create_superuser(
            username="adminuser",
            password="adminpassword123",
            inactivity_policy=User.InactivityPolicy.ONE_WEEK,
        )
        superuser.last_login = self.now - timedelta(days=30)
        superuser.save()

        self.assertFalse(superuser.is_inactive_due_to_policy())
        deactivated = check_and_deactivate_inactive_users()
        self.assertEqual(deactivated, 0)
        superuser.refresh_from_db()
        self.assertTrue(superuser.is_active)

    def test_login_form_deactivates_and_rejects_inactive_user(self):
        self.user.inactivity_policy = User.InactivityPolicy.ONE_WEEK
        self.user.last_login = self.now - timedelta(days=9)
        self.user.save()

        factory = RequestFactory()
        request = factory.post("/login/")

        form = PortalAuthenticationForm(
            request,
            data={"username": "testuser", "password": "testpassword123"},
        )
        self.assertFalse(form.is_valid())
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        error_msg = str(form.errors)
        self.assertIn("deactivated due to inactivity", error_msg)
