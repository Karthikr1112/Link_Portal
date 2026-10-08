from datetime import timedelta
from django.test import TestCase, RequestFactory
from django.utils import timezone

from portal.models import InactivityPeriod, User
from portal.services import check_and_deactivate_inactive_users
from portal.forms import PortalAuthenticationForm


class UserInactivityPeriodTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.period_1_day = InactivityPeriod.objects.create(name="1 Day", days=1)
        self.period_2_days = InactivityPeriod.objects.create(name="2 Days", days=2)
        self.period_3_days = InactivityPeriod.objects.create(name="3 Days", days=3)
        self.period_1_week = InactivityPeriod.objects.create(name="1 Week", days=7)
        self.period_10_days = InactivityPeriod.objects.create(name="10 Days", days=10)

        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123",
            is_active=True,
            inactivity_period=None,  # No Deactivation by default
        )

    def test_default_none_period_never_deactivates(self):
        # Inactive for 50 days
        self.user.last_login = self.now - timedelta(days=50)
        self.user.save()

        self.assertFalse(self.user.is_inactive_due_to_policy())
        deactivated = check_and_deactivate_inactive_users()
        self.assertEqual(deactivated, 0)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_dynamic_period_1_day(self):
        self.user.inactivity_period = self.period_1_day
        # Within 1 day
        self.user.last_login = self.now - timedelta(hours=12)
        self.user.save()
        self.assertFalse(self.user.is_inactive_due_to_policy())

        # Exceeded 1 day (e.g. 2 days inactive)
        self.user.last_login = self.now - timedelta(days=2)
        self.user.save()
        self.assertTrue(self.user.is_inactive_due_to_policy())

        deactivated = check_and_deactivate_inactive_users()
        self.assertEqual(deactivated, 1)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_dynamic_period_3_days(self):
        self.user.inactivity_period = self.period_3_days
        # Inactive for 2 days
        self.user.last_login = self.now - timedelta(days=2)
        self.user.save()
        self.assertFalse(self.user.is_inactive_due_to_policy())

        # Inactive for 4 days
        self.user.last_login = self.now - timedelta(days=4)
        self.user.save()
        self.assertTrue(self.user.is_inactive_due_to_policy())

        deactivated = check_and_deactivate_inactive_users()
        self.assertEqual(deactivated, 1)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_manual_activation_resets_inactivity_timer(self):
        self.user.inactivity_period = self.period_1_week
        self.user.last_login = self.now - timedelta(days=10)
        self.user.is_active = False
        self.user.save()

        # Admin manually activates account
        self.user.is_active = True
        self.user.save()

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertIsNotNone(self.user.last_activated_at)
        self.assertEqual(self.user.days_inactive, 0)
        self.assertFalse(self.user.is_inactive_due_to_policy())

    def test_superuser_is_never_deactivated(self):
        superuser = User.objects.create_superuser(
            username="adminuser",
            password="adminpassword123",
            inactivity_period=self.period_1_day,
        )
        superuser.last_login = self.now - timedelta(days=30)
        superuser.save()

        self.assertFalse(superuser.is_inactive_due_to_policy())
        deactivated = check_and_deactivate_inactive_users()
        self.assertEqual(deactivated, 0)
        superuser.refresh_from_db()
        self.assertTrue(superuser.is_active)

    def test_login_form_deactivates_and_rejects_inactive_user(self):
        self.user.inactivity_period = self.period_1_week
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
