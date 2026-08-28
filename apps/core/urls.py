from django.urls import path

from .health import health_check
from .views import home, management_dashboard, statistics_dashboard

app_name = "core"

urlpatterns = [
    path("", home, name="home"),
    path("statistics/", statistics_dashboard, name="statistics"),
    path("management/", management_dashboard, name="management_dashboard"),
    path("healthz/", health_check, name="health"),
]
