from django.urls import path

from . import views

app_name = "climbs"

urlpatterns = [
    path("users/", views.user_list, name="user_list"),
    path("ascents/new/", views.ascent_create, name="ascent_create"),
    path("ascents/<int:pk>/edit/", views.ascent_edit, name="ascent_edit"),
    path("ascents/<int:pk>/delete/", views.ascent_delete, name="ascent_delete"),
    path("walls/", views.wall_list, name="wall_list"),
    path("walls/new/", views.wall_create, name="wall_create"),
    path("walls/<int:pk>/", views.wall_detail, name="wall_detail"),
    path("walls/<int:pk>/edit/", views.wall_edit, name="wall_edit"),
    path("walls/<int:pk>/archive/", views.wall_archive, name="wall_archive"),
    path("walls/<int:pk>/delete/", views.wall_delete, name="wall_delete"),
    path("routes/", views.route_list, name="route_list"),
    path("routes/new/", views.route_create, name="route_create"),
    path("routes/<int:pk>/", views.route_detail, name="route_detail"),
    path("routes/<int:pk>/edit/", views.route_edit, name="route_edit"),
    path("routes/<int:pk>/archive/", views.route_archive, name="route_archive"),
    path("routes/<int:pk>/delete/", views.route_delete, name="route_delete"),
    path("routes/<int:pk>/image/", views.route_image_upload, name="route_image_upload"),
    path(
        "routes/<int:pk>/annotation/",
        views.route_annotation_edit,
        name="route_annotation_edit",
    ),
    path(
        "routes/<int:pk>/image/delete/",
        views.route_image_delete,
        name="route_image_delete",
    ),
]
