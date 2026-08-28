from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("register/sent/", views.verification_sent, name="verification_sent"),
    path("register/resend/", views.resend_verification, name="resend_verification"),
    path("verify-email/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path("login/", views.ClimbingSideLoginView.as_view(), name="login"),
    path("logout/", views.ClimbingSideLogoutView.as_view(), name="logout"),
    path("account/", views.profile, name="profile"),
    path("account/edit/", views.edit_profile, name="profile_edit"),
    path("account/password/", views.PasswordChangeView.as_view(), name="password_change"),
    path(
        "account/password/done/",
        views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path("password-reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path(
        "password-reset/sent/",
        views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("users/<str:username>/", views.public_profile, name="public_profile"),
]
