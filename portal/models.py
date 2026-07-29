from django.contrib.auth.models import AbstractUser
from django.db import models


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

    class Meta:
        indexes = [
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.username


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
