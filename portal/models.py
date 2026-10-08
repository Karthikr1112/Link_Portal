from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name


class Store(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name


class InactivityPeriod(models.Model):
    name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional label (e.g. '1 Day', '1 Week'). If blank, will default to '[X] Days'.",
    )
    days = models.PositiveIntegerField(
        unique=True,
        help_text="Number of days of inactivity before automatic deactivation (e.g., 1, 2, 3, 7, 10).",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this period option is active and available in selection dropdowns.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["days"]
        verbose_name = "Inactivity Period"
        verbose_name_plural = "Inactivity Periods"

    def save(self, *args, **kwargs):
        if not self.name:
            suffix = "Day" if self.days == 1 else "Days"
            self.name = f"{self.days} {suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        suffix = "Day" if self.days == 1 else "Days"
        if self.name and self.name != f"{self.days} {suffix}":
            return f"{self.name} ({self.days} {suffix})"
        return self.name or f"{self.days} {suffix}"


class User(AbstractUser):
    categories = models.ManyToManyField(
        Category,
        related_name="users",
        blank=True,
        help_text="Categories this user belongs to. Determines which links they can see.",
    )
    stores = models.ManyToManyField(
        Store,
        related_name="users",
        blank=True,
    )
    inactivity_period = models.ForeignKey(
        InactivityPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="Inactivity Period",
        help_text="Select an inactivity option, or leave empty for No Deactivation.",
    )
    last_activated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Last Activated At",
        help_text="Timestamp of when the user was manually activated or joined.",
    )

    class Meta:
        indexes = [
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.username

    def get_inactivity_threshold_days(self):
        """Returns the number of days allowed for inactivity before deactivation."""
        if self.inactivity_period and self.inactivity_period.is_active:
            return self.inactivity_period.days
        return None

    @property
    def effective_last_activity(self):
        """
        Determines the baseline activity timestamp.
        - If the user was manually reactivated after their last login, use last_activated_at.
        - Otherwise, if the user has logged in before, use last_login.
        - If the user has never logged in, use last_activated_at (if set) or date_joined.
        """
        if self.last_activated_at and self.last_login:
            return max(self.last_login, self.last_activated_at)
        if self.last_login:
            return self.last_login
        if self.last_activated_at:
            return self.last_activated_at
        return self.date_joined

    @property
    def days_inactive(self):
        """Returns integer days elapsed since effective last activity."""
        baseline = self.effective_last_activity
        if not baseline:
            return 0
        delta = timezone.now() - baseline
        return max(0, delta.days)

    def is_inactive_due_to_policy(self):
        """
        Returns True if the user is not a superuser, has an active policy,
        and has exceeded the inactivity threshold.
        """
        if self.is_superuser:
            return False
        threshold = self.get_inactivity_threshold_days()
        if threshold is None:
            return False
        baseline = self.effective_last_activity
        if not baseline:
            return False
        return (timezone.now() - baseline) >= timezone.timedelta(days=threshold)

    def save(self, *args, **kwargs):
        # When an inactive user is manually activated (is_active goes False -> True),
        # record last_activated_at to reset their inactivity timer.
        if self.pk:
            orig = User.objects.filter(pk=self.pk).values("is_active").first()
            if orig and not orig["is_active"] and self.is_active:
                self.last_activated_at = timezone.now()
                if "update_fields" in kwargs and kwargs["update_fields"] is not None:
                    kwargs["update_fields"] = set(kwargs["update_fields"]) | {"last_activated_at"}
        super().save(*args, **kwargs)


class Link(models.Model):
    title = models.CharField(max_length=150)
    url = models.URLField(max_length=500)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    categories = models.ManyToManyField(
        Category,
        related_name="links",
        blank=True,
    )
    stores = models.ManyToManyField(
        Store,
        related_name="links",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "title"]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["order"]),
        ]

    def __str__(self):
        return self.title
