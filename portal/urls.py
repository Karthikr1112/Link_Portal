from django.contrib.auth import views as auth_views
from django.urls import path

from .views import DashboardView, PortalLoginView

app_name = "portal"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path(
        "login/",
        PortalLoginView.as_view(),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
