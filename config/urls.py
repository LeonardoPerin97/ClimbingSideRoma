from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core.views import set_language_preference

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/setlang/", set_language_preference, name="set_language"),
    path("", include("apps.accounts.urls")),
    path("", include("apps.climbs.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
