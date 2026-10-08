from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.shortcuts import redirect
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from .models import Category, InactivityPeriod, Link, Store, User
from .services import check_and_deactivate_inactive_users


@admin.register(InactivityPeriod)
class InactivityPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "days", "is_active", "user_count", "created_at")
    list_editable = ("days", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)

    def user_count(self, obj):
        return obj.users.count()


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
        (
            "Inactivity & Account Deactivation",
            {
                "fields": ("inactivity_period", "last_activated_at"),
                "description": "Configure automatic account deactivation based on inactivity.",
            },
        ),
        ("Categories & Stores", {"fields": ("categories", "stores")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Inactivity Period", {"fields": ("inactivity_period",)}),
        ("Categories & Stores", {"fields": ("categories", "stores")}),
    )
    readonly_fields = UserAdmin.readonly_fields + ("last_activated_at",)
    filter_horizontal = UserAdmin.filter_horizontal + ("categories", "stores")
    list_display = (
        "username",
        "email",
        "is_active",
        "inactivity_period",
        "inactivity_status",
        "last_login",
        "is_staff",
        "category_list",
        "store_list",
    )
    list_editable = ("is_active", "inactivity_period")
    list_filter = UserAdmin.list_filter + ("inactivity_period", "categories", "stores")

    actions = [
        "activate_users",
        "deactivate_users",
        "set_period_none",
        "apply_all_period_none",
        "run_inactivity_check_action",
    ]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "inactivity_period":
            kwargs["queryset"] = InactivityPeriod.objects.filter(is_active=True).order_by("days")
            kwargs["empty_label"] = "No Deactivation"
            formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
            if formfield and hasattr(formfield, "widget"):
                formfield.widget.can_add_related = False
                formfield.widget.can_change_related = False
                formfield.widget.can_delete_related = False
                formfield.widget.can_view_related = False
            return formfield
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("categories", "stores").select_related("inactivity_period")

    def changelist_view(self, request, extra_context=None):
        check_and_deactivate_inactive_users()
        extra_context = extra_context or {}
        extra_context["available_periods"] = InactivityPeriod.objects.filter(is_active=True).order_by("days")
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "bulk-set-policy/",
                self.admin_site.admin_view(self.bulk_set_policy_view),
                name="portal_user_bulk_set_policy",
            ),
            path(
                "run-inactivity-check/",
                self.admin_site.admin_view(self.run_inactivity_check_view),
                name="portal_user_run_inactivity_check",
            ),
        ]
        return custom_urls + urls

    def bulk_set_policy_view(self, request):
        if request.method == "POST":
            period_id = request.POST.get("period_id")
            if period_id:
                try:
                    period = InactivityPeriod.objects.get(pk=period_id)
                    count = User.objects.filter(is_superuser=False).update(inactivity_period=period)
                    deactivated = check_and_deactivate_inactive_users()
                    msg = f"Inactivity period updated to '{period}' for all {count} regular user(s)."
                    if deactivated:
                        msg += f" {deactivated} inactive user(s) were automatically deactivated."
                    self.message_user(request, msg, level=messages.SUCCESS)
                except InactivityPeriod.DoesNotExist:
                    self.message_user(request, "Selected period does not exist.", level=messages.ERROR)
            else:
                count = User.objects.filter(is_superuser=False).update(inactivity_period=None)
                self.message_user(request, f"Set to 'No Deactivation' for all {count} regular user(s).", level=messages.SUCCESS)
        return redirect("admin:portal_user_changelist")

    def run_inactivity_check_view(self, request):
        deactivated = check_and_deactivate_inactive_users()
        if deactivated:
            self.message_user(
                request,
                f"Inactivity check completed. {deactivated} user account(s) deactivated.",
                level=messages.WARNING,
            )
        else:
            self.message_user(
                request,
                "Inactivity check completed. All accounts are compliant with their policies.",
                level=messages.SUCCESS,
            )
        return redirect("admin:portal_user_changelist")

    @admin.display(description="Inactivity Status")
    def inactivity_status(self, obj):
        if obj.is_superuser:
            return format_html(
                '<span class="badge badge-secondary" style="background:#64748b; color:#fff; padding:4px 8px; border-radius:4px;">Superuser (Exempt)</span>'
            )

        threshold = obj.get_inactivity_threshold_days()
        days = obj.days_inactive

        if not threshold:
            return format_html(
                '<span class="badge" style="background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; padding:4px 8px; border-radius:4px;">No Deactivation ({}d inactive)</span>',
                days,
            )

        if not obj.is_active:
            return format_html(
                '<span class="badge badge-danger" style="background:#dc2626; color:#fff; padding:4px 8px; border-radius:4px;"><i class="fas fa-user-slash mr-1"></i> Deactivated ({}d / {}d limit)</span>',
                days,
                threshold,
            )

        remaining = max(0, threshold - days)
        if remaining <= 2:
            return format_html(
                '<span class="badge badge-warning" style="background:#d97706; color:#fff; padding:4px 8px; border-radius:4px;"><i class="fas fa-exclamation-triangle mr-1"></i> Active ({}d inactive - {}d left)</span>',
                days,
                remaining,
            )

        return format_html(
            '<span class="badge badge-success" style="background:#16a34a; color:#fff; padding:4px 8px; border-radius:4px;"><i class="fas fa-check-circle mr-1"></i> Active ({}d / {}d limit)</span>',
            days,
            threshold,
        )

    def category_list(self, obj):
        return ", ".join(c.name for c in obj.categories.all())

    def store_list(self, obj):
        return ", ".join(s.name for s in obj.stores.all())

    # --- Admin Actions ---
    @admin.action(description="Activate selected users (Reset timer)")
    def activate_users(self, request, queryset):
        now = timezone.now()
        count = 0
        for u in queryset:
            u.is_active = True
            u.last_activated_at = now
            u.save(update_fields=["is_active", "last_activated_at"])
            count += 1
        self.message_user(request, f"{count} user(s) successfully activated.", level=messages.SUCCESS)

    @admin.action(description="Deactivate selected users")
    def deactivate_users(self, request, queryset):
        count = queryset.filter(is_superuser=False).update(is_active=False)
        self.message_user(request, f"{count} user(s) deactivated.", level=messages.INFO)

    @admin.action(description="Set to No Deactivation (Selected users)")
    def set_period_none(self, request, queryset):
        count = queryset.update(inactivity_period=None)
        self.message_user(request, f"Set to 'No Deactivation' for {count} user(s).", level=messages.SUCCESS)

    @admin.action(description="Apply to ALL users: No Deactivation")
    def apply_all_period_none(self, request, queryset):
        count = User.objects.filter(is_superuser=False).update(inactivity_period=None)
        self.message_user(request, f"Applied 'No Deactivation' to all {count} regular user(s).", level=messages.SUCCESS)

    @admin.action(description="Run inactivity check now")
    def run_inactivity_check_action(self, request, queryset):
        deactivated = check_and_deactivate_inactive_users()
        self.message_user(
            request,
            f"Inactivity check executed. {deactivated} user(s) deactivated.",
            level=messages.INFO,
        )
