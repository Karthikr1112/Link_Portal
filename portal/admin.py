from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Category, Link, Store, User


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "user_count", "link_count", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("users", "links")

    def user_count(self, obj):
        return obj.users.count()

    def link_count(self, obj):
        return obj.links.count()


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "user_count", "link_count")
    list_filter = ("is_active",)
    search_fields = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("users", "links")

    def user_count(self, obj):
        return obj.users.count()

    def link_count(self, obj):
        return obj.links.count()


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    fields = ("title", "url", "categories", "stores")
    list_display = ("title", "category_list", "store_list")
    list_filter = ("categories", "stores")
    search_fields = ("title", "url")
    filter_horizontal = ("categories", "stores")
    ordering = ("order", "title")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("categories", "stores")

    def category_list(self, obj):
        return ", ".join(c.name for c in obj.categories.all())

    def store_list(self, obj):
        return ", ".join(s.name for s in obj.stores.all())


@admin.register(User)
class PortalUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Categories & Stores", {"fields": ("categories", "stores")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Categories & Stores", {"fields": ("categories", "stores")}),
    )
    filter_horizontal = UserAdmin.filter_horizontal + ("categories", "stores")
    list_display = ("username", "email", "is_staff", "is_active", "category_list", "store_list")
    list_filter = UserAdmin.list_filter + ("categories", "stores")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("categories", "stores")

    def category_list(self, obj):
        return ", ".join(c.name for c in obj.categories.all())

    def store_list(self, obj):
        return ", ".join(s.name for s in obj.stores.all())
