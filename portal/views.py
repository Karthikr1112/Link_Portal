from itertools import groupby

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.views.generic import TemplateView

from .models import Category, Link


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "portal/dashboard.html"
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        allowed_store_ids = None
        if user.is_superuser:
            categories = Category.objects.filter(is_active=True)
            link_queryset = Link.objects.filter(is_active=True)
        else:
            categories = user.categories.filter(is_active=True)
            allowed_store_ids = set(user.stores.values_list("id", flat=True))
            link_queryset = Link.objects.filter(is_active=True).filter(
                Q(stores__in=allowed_store_ids) | Q(stores__isnull=True)
            )

        active_links = Prefetch(
            "links",
            queryset=link_queryset.order_by("order", "title")
            .prefetch_related("stores")
            .distinct(),
        )
        rows = [
            (category, link)
            for category in categories.prefetch_related(active_links)
            for link in category.links.all()
        ]

        page_obj = Paginator(rows, self.paginate_by).get_page(self.request.GET.get("page"))

        grouped_links = []
        for category, category_rows in groupby(page_obj.object_list, key=lambda row: row[0]):
            store_groups = {}
            store_order = []
            for _, link in category_rows:
                stores = list(link.stores.all())
                if allowed_store_ids is not None:
                    stores = [s for s in stores if s.id in allowed_store_ids]
                stores = stores or [None]
                for store in stores:
                    key = store.id if store else None
                    if key not in store_groups:
                        store_groups[key] = {"store": store, "links": []}
                        store_order.append(key)
                    store_groups[key]["links"].append(link)
            grouped_links.append((category, [store_groups[key] for key in store_order]))

        context["grouped_links"] = grouped_links
        context["page_obj"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages()
        return context
