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


class User(AbstractUser):
    class InactivityPolicy(models.TextChoices):
        NEVER = "none", "No Deactivation"
        ONE_WEEK = "7_days", "1 Week"
        TEN_DAYS = "10_days", "10 Days"

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
    inactivity_policy = models.CharField(
        max_length=20,
        choices=InactivityPolicy.choices,
        default=InactivityPolicy.NEVER,
        verbose_name="Deactivation Policy",
        help_text="Automatically deactivate the account if not logged in for this duration.",
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
            models.Index(fields=["inactivity_policy"]),
        ]

    def __str__(self):
        return self.username

    def get_inactivity_threshold_days(self):
        """Returns the number of days allowed for inactivity before deactivation."""
        if self.inactivity_policy == self.InactivityPolicy.ONE_WEEK:
            return 7
        elif self.inactivity_policy == self.InactivityPolicy.TEN_DAYS:
            return 10
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
