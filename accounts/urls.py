"""URLs for accounts app."""
from django.urls import path

from accounts.views import (
    EmailTokenObtainPairView,
    EmailVerificationConfirmView,
    EmailVerificationRequestView,
    ExpertListView,
    FCMTokenUpdateView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    UserListView,
)

urlpatterns = [
    path("token/", EmailTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("register/", RegisterView.as_view(), name="register"),
    path("users/", UserListView.as_view(), name="users"),
    path("experts/", ExpertListView.as_view(), name="experts"),
    path("update-fcm-token/", FCMTokenUpdateView.as_view(), name="update-fcm-token"),
    path("verify-email/request/", EmailVerificationRequestView.as_view(), name="verify-email-request"),
    path("verify-email/confirm/", EmailVerificationConfirmView.as_view(), name="verify-email-confirm"),
    path("password-reset/request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
]
