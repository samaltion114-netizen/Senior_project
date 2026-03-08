"""Views for user registration and profile access."""
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import EmailVerificationToken, PasswordResetToken
from accounts.serializers import (
    EmailVerificationConfirmSerializer,
    EmailVerificationRequestSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(APIView):
    """Register endpoint."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(request=RegisterSerializer, responses={201: UserSerializer})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = EmailVerificationToken.objects.create(user=user)
        print(f"[email-verification] user={user.email} token={token.token}")
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class UserListView(generics.ListAPIView):
    """List all users for trainer/admin usage."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = User.objects.all().order_by("id")


class EmailVerificationRequestView(APIView):
    """Issue a new email verification token."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(request=EmailVerificationRequestSerializer, responses={200: dict})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = EmailVerificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email=email).first()
        if user:
            token = EmailVerificationToken.objects.create(user=user)
            print(f"[email-verification] user={email} token={token.token}")
        return Response({"detail": "If the account exists, a verification token has been issued."})


class EmailVerificationConfirmView(APIView):
    """Verify email using one-time token."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(request=EmailVerificationConfirmSerializer, responses={200: dict})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = EmailVerificationConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = EmailVerificationToken.objects.get(token=serializer.validated_data["token"], used=False)
        token.used = True
        token.save(update_fields=["used"])
        user = token.user
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        return Response({"detail": "Email verified successfully."})


class PasswordResetRequestView(APIView):
    """Issue password reset token."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(request=PasswordResetRequestSerializer, responses={200: dict})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email=email).first()
        if user:
            token = PasswordResetToken.objects.create(user=user)
            print(f"[password-reset] user={email} token={token.token}")
        return Response({"detail": "If the account exists, a reset token has been issued."})


class PasswordResetConfirmView(APIView):
    """Reset password using one-time token."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(request=PasswordResetConfirmSerializer, responses={200: dict})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = PasswordResetToken.objects.get(token=serializer.validated_data["token"], used=False)
        if token.expires_at <= timezone.now():
            return Response({"detail": "Token expired."}, status=status.HTTP_400_BAD_REQUEST)
        user = token.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        token.used = True
        token.save(update_fields=["used"])
        return Response({"detail": "Password has been reset successfully."})


@login_required
def profile_view(request):
    """Simple web profile endpoint used by Django login redirects."""
    user = request.user
    student_profile = getattr(user, "student_profile", None)
    return JsonResponse(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_student": user.is_student,
            "is_expert": user.is_expert,
            "is_trainer": user.is_trainer,
            "major": student_profile.major if student_profile else "",
            "current_status": student_profile.current_status if student_profile else "",
        }
    )
