"""URLs for accounts app."""
from django.urls import path

from accounts.views import (
    EmailVerificationConfirmView,
    EmailVerificationRequestView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    UserListView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("users/", UserListView.as_view(), name="users"),
    path("verify-email/request/", EmailVerificationRequestView.as_view(), name="verify-email-request"),
    path("verify-email/confirm/", EmailVerificationConfirmView.as_view(), name="verify-email-confirm"),
    path("password-reset/request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
]
