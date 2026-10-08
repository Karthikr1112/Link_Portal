from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import User


class PortalAuthenticationForm(AuthenticationForm):
    """
    Custom authentication form that provides clear feedback when an account
    is deactivated due to inactivity, and enforces deactivation at the time of login.
    """

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )

            if self.user_cache is None:
                # Check if user exists and password is correct, but account is inactive
                try:
                    user = User.objects.get(username=username)
                    if user.check_password(password):
                        # Password is correct, but account is deactivated
                        if not user.is_active:
                            threshold = user.get_inactivity_threshold_days()
                            if threshold:
                                raise ValidationError(
                                    f"Your account has been deactivated due to inactivity (not logged in for {threshold} days). "
                                    "Please contact your administrator to manually reactivate your account.",
                                    code="inactive_due_to_inactivity",
                                )
                            raise ValidationError(
                                "Your account is currently deactivated. Please contact your administrator to activate it.",
                                code="inactive",
                            )
                except User.DoesNotExist:
                    pass

                raise self.get_invalid_login_error()
            else:
                # User credentials valid and user is currently active.
                # Check if they have exceeded their inactivity policy threshold!
                if self.user_cache.is_inactive_due_to_policy():
                    self.user_cache.is_active = False
                    self.user_cache.save(update_fields=["is_active"])
                    threshold = self.user_cache.get_inactivity_threshold_days()
                    raise ValidationError(
                        f"Your account has been deactivated due to inactivity (not logged in for {threshold} days). "
                        "Please contact your administrator to manually reactivate your account.",
                        code="inactive_due_to_inactivity",
                    )
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data
