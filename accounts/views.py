"""Views for user registration and profile access."""
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView

from accounts.models import (
    ChatMessage,
    ChatThread,
    EmailVerificationToken,
    ExpertAssignment,
    ExpertProfile,
    Notification,
    PasswordResetToken,
    PaymentRecord,
    UserBadge,
)
from accounts.permissions import IsExpert, IsStudent
from accounts.serializers import (
    AssignmentActionSerializer,
    AssignmentRequestSerializer,
    ChatMessageCreateSerializer,
    ChatMessageSerializer,
    ChatThreadSerializer,
    EmailVerificationConfirmSerializer,
    EmailVerificationRequestSerializer,
    EmailTokenObtainPairSerializer,
    ExpertAssignmentSerializer,
    ExpertListSerializer,
    FCMTokenUpdateSerializer,
    NotificationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PaymentIntentRequestSerializer,
    PaymentRecordSerializer,
    RegisterSerializer,
    StripeWebhookSerializer,
    UserBadgeSerializer,
    UserSerializer,
)
from accounts.services import create_notification, log_user_activity

try:
    import stripe
except Exception:  # pragma: no cover - optional dependency fallback
    stripe = None

User = get_user_model()


class EmailTokenObtainPairView(TokenObtainPairView):
    """JWT login view using email + password."""

    serializer_class = EmailTokenObtainPairSerializer


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
    """List all users for authenticated usage."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = User.objects.all().order_by("id")


class ExpertListView(generics.ListAPIView):
    """List experts for marketplace screens with optional name search."""

    serializer_class = ExpertListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        search = self.request.query_params.get("search", "").strip()
        queryset = ExpertProfile.objects.select_related("user").all().order_by("user__username")
        queryset = queryset.filter(is_accepting_new_students=True)
        if search:
            queryset = queryset.filter(Q(user__username__icontains=search) | Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search))
        return queryset


class FCMTokenUpdateView(APIView):
    """Persist the current user's mobile push token."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=FCMTokenUpdateSerializer, responses={200: dict})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = FCMTokenUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.fcm_token = serializer.validated_data["fcm_token"]
        request.user.save(update_fields=["fcm_token"])
        return Response({"detail": "FCM token updated."})


class LeaderboardView(APIView):
    """Return simple XP-based leaderboard with optional date filters."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        filter_name = request.query_params.get("filter", "all").lower()
        queryset = User.objects.filter(is_student=True).order_by("-total_xp", "-current_streak", "id")
        rows = []
        for index, user in enumerate(queryset[:50], start=1):
            rows.append(
                {
                    "rank": index,
                    "user_id": user.id,
                    "user_name": user.username,
                    "total_xp": user.total_xp,
                    "current_streak": user.current_streak,
                    "filter": filter_name,
                }
            )
        return Response({"results": rows})


class UserBadgesView(APIView):
    """Return all badges earned by one user."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id: int, *args, **kwargs) -> Response:
        badges = UserBadge.objects.filter(user_id=id).select_related("badge")
        return Response(UserBadgeSerializer(badges, many=True).data)


class NotificationListView(APIView):
    """List current user's notifications."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        queryset = Notification.objects.filter(user=request.user)
        return Response(NotificationSerializer(queryset, many=True).data)


class AssignmentListView(APIView):
    """List assignments relevant to the current user."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        queryset = ExpertAssignment.objects.filter(Q(student=request.user) | Q(expert=request.user)).order_by("-created_at")
        return Response(ExpertAssignmentSerializer(queryset, many=True).data)


class AssignmentRequestView(APIView):
    """Student requests collaboration with an expert."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @extend_schema(request=AssignmentRequestSerializer, responses={201: ExpertAssignmentSerializer})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = AssignmentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expert = User.objects.filter(id=serializer.validated_data["expert_id"], is_expert=True).first()
        if expert is None:
            return Response({"detail": "Expert not found."}, status=status.HTTP_404_NOT_FOUND)
        assignment = ExpertAssignment.objects.create(
            student=request.user,
            expert=expert,
            request_message=serializer.validated_data.get("request_message", ""),
        )
        create_notification(
            user=expert,
            type=Notification.TYPE_ASSIGNMENT_REQUEST,
            title="طلب إشراف جديد",
            message=f"يرغب الطالب {request.user.username} في الانضمام إليك، هل تقبل؟",
            related_id=assignment.id,
        )
        log_user_activity(user=request.user, event_type="assignment_requested", related_id=assignment.id)
        return Response(ExpertAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)


class TrainerAssignmentAcceptView(APIView):
    """Expert accepts a student assignment request."""

    permission_classes = [permissions.IsAuthenticated, IsExpert]

    def post(self, request, id: int, *args, **kwargs) -> Response:
        assignment = ExpertAssignment.objects.filter(id=id, expert=request.user).first()
        if assignment is None:
            return Response({"detail": "Assignment not found."}, status=status.HTTP_404_NOT_FOUND)
        assignment.status = ExpertAssignment.STATUS_AWAITING_PAYMENT
        assignment.expires_at = None
        assignment.rejection_reason = ""
        assignment.save(update_fields=["status", "expires_at", "rejection_reason", "updated_at"])
        create_notification(
            user=assignment.student,
            type=Notification.TYPE_ASSIGNMENT_ACCEPTED,
            title="Assignment accepted",
            message=f"{request.user.username} accepted your request. Complete payment to start chat.",
            related_id=assignment.id,
        )
        log_user_activity(user=assignment.student, event_type="assignment_accepted", related_id=assignment.id)
        return Response(ExpertAssignmentSerializer(assignment).data)


class TrainerAssignmentRejectView(APIView):
    """Expert rejects a student assignment request."""

    permission_classes = [permissions.IsAuthenticated, IsExpert]

    @extend_schema(request=AssignmentActionSerializer, responses={200: ExpertAssignmentSerializer})
    def post(self, request, id: int, *args, **kwargs) -> Response:
        assignment = ExpertAssignment.objects.filter(id=id, expert=request.user).first()
        if assignment is None:
            return Response({"detail": "Assignment not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = AssignmentActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment.status = ExpertAssignment.STATUS_REJECTED
        assignment.rejection_reason = serializer.validated_data.get("reason", "")
        assignment.save(update_fields=["status", "rejection_reason", "updated_at"])
        create_notification(
            user=assignment.student,
            type=Notification.TYPE_ASSIGNMENT_REJECTED,
            title="Assignment rejected",
            message=f"{request.user.username} rejected your mentorship request.",
            related_id=assignment.id,
            metadata={"reason": assignment.rejection_reason},
        )
        return Response(ExpertAssignmentSerializer(assignment).data)


class ChatThreadListView(APIView):
    """List active chat threads for the current user."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        queryset = ChatThread.objects.filter(
            assignment__status=ExpertAssignment.STATUS_ACTIVE
        ).filter(Q(assignment__student=request.user) | Q(assignment__expert=request.user)).select_related("assignment__student", "assignment__expert")
        return Response(ChatThreadSerializer(queryset, many=True).data)


class ChatMessageListCreateView(APIView):
    """List or send messages inside an active mentorship thread."""

    permission_classes = [permissions.IsAuthenticated]

    def get_thread(self, request, id: int) -> ChatThread | None:
        return ChatThread.objects.filter(
            id=id,
            assignment__status=ExpertAssignment.STATUS_ACTIVE,
        ).filter(Q(assignment__student=request.user) | Q(assignment__expert=request.user)).first()

    def get(self, request, id: int, *args, **kwargs) -> Response:
        thread = self.get_thread(request, id)
        if thread is None:
            return Response({"detail": "Thread not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ChatMessageSerializer(thread.messages.all(), many=True).data)

    @transaction.atomic
    @extend_schema(request=ChatMessageCreateSerializer, responses={201: ChatMessageSerializer})
    def post(self, request, id: int, *args, **kwargs) -> Response:
        thread = self.get_thread(request, id)
        if thread is None:
            return Response({"detail": "Thread not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ChatMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = ChatMessage.objects.create(thread=thread, sender=request.user, body=serializer.validated_data["body"])
        recipient = thread.assignment.expert if request.user == thread.assignment.student else thread.assignment.student
        create_notification(
            user=recipient,
            type=Notification.TYPE_CHAT_MESSAGE,
            title="New chat message",
            message=f"{request.user.username} sent you a new message.",
            related_id=thread.id,
        )
        thread.save(update_fields=["updated_at"])
        return Response(ChatMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class PaymentIntentView(APIView):
    """Create Stripe payment intent payload for Flutter payment sheet."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=PaymentIntentRequestSerializer, responses={200: dict})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = PaymentIntentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        assignment = None
        if data.get("assignment_id"):
            assignment = ExpertAssignment.objects.filter(
                id=data["assignment_id"],
                student=request.user,
                status=ExpertAssignment.STATUS_AWAITING_PAYMENT,
            ).select_related("expert__expert_profile").first()
            if assignment is None:
                return Response({"detail": "Assignment not found or not payable."}, status=status.HTTP_404_NOT_FOUND)
        expert = assignment.expert if assignment else (User.objects.filter(id=data.get("expert_id"), is_expert=True).first() if data.get("expert_id") else None)
        amount = data.get("amount")
        if amount is None:
            if assignment and hasattr(assignment.expert, "expert_profile"):
                amount = int(float(assignment.expert.expert_profile.subscription_price) * 100)
            else:
                return Response({"detail": "amount is required."}, status=status.HTTP_400_BAD_REQUEST)
        if stripe is None:
            payment = PaymentRecord.objects.create(
                user=request.user,
                expert=expert,
                provider="mock",
                amount=amount,
                currency=data["currency"],
                payment_intent_id=f"mock_pi_{request.user.id}_{timezone.now().timestamp()}",
                client_secret=f"mock_client_secret_{amount}_{data['currency']}",
                status=PaymentRecord.STATUS_PENDING,
                metadata={"assignment_id": assignment.id if assignment else None},
            )
            return Response(
                {
                    "provider": "mock",
                    "client_secret": payment.client_secret,
                    "payment_intent_id": payment.payment_intent_id,
                    "publishable_key": "",
                }
            )
        stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=data["currency"],
            metadata={"user_id": request.user.id, "expert_id": data.get("expert_id", "")},
        )
        PaymentRecord.objects.update_or_create(
            payment_intent_id=intent.id,
            defaults={
                "user": request.user,
                "expert": expert,
                "provider": "stripe",
                "amount": amount,
                "currency": data["currency"],
                "client_secret": intent.client_secret,
                "status": PaymentRecord.STATUS_PENDING,
                "metadata": {"expert_id": data.get("expert_id", ""), "assignment_id": assignment.id if assignment else None},
            },
        )
        return Response(
            {
                "provider": "stripe",
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
            }
        )


class PaymentRecordListView(APIView):
    """List current user's payment records."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        queryset = PaymentRecord.objects.filter(user=request.user)
        return Response(PaymentRecordSerializer(queryset, many=True).data)


class StripeWebhookView(APIView):
    """Update payment record status from webhook-like payload."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(request=StripeWebhookSerializer, responses={200: PaymentRecordSerializer})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = StripeWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payment = PaymentRecord.objects.filter(payment_intent_id=data["payment_intent_id"]).first()
        if payment is None:
            return Response({"detail": "Payment record not found."}, status=status.HTTP_404_NOT_FOUND)
        payment.status = PaymentRecord.STATUS_SUCCEEDED if data["status"] == "succeeded" else PaymentRecord.STATUS_FAILED
        payment.metadata = {**payment.metadata, **data.get("metadata", {})}
        payment.save(update_fields=["status", "metadata", "updated_at"])
        if payment.status == PaymentRecord.STATUS_SUCCEEDED:
            assignment_id = payment.metadata.get("assignment_id")
            if assignment_id:
                assignment = ExpertAssignment.objects.filter(
                    id=assignment_id,
                    student=payment.user,
                    expert=payment.expert,
                    status=ExpertAssignment.STATUS_AWAITING_PAYMENT,
                ).first()
                if assignment is not None:
                    assignment.status = ExpertAssignment.STATUS_ACTIVE
                    assignment.expires_at = timezone.now() + timedelta(days=30)
                    assignment.save(update_fields=["status", "expires_at", "updated_at"])
                    ChatThread.objects.get_or_create(assignment=assignment)
                    if payment.expert and hasattr(payment.expert, "expert_profile"):
                        profile = payment.expert.expert_profile
                        profile.wallet_balance = (profile.wallet_balance or Decimal("0")) + (Decimal(payment.amount) / Decimal("100"))
                        profile.save(update_fields=["wallet_balance"])
        return Response(PaymentRecordSerializer(payment).data)


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
            "user_name": user.username,
            "email": user.email,
            "is_student": user.is_student,
            "is_expert": user.is_expert,
            "total_xp": user.total_xp,
            "current_streak": user.current_streak,
            "highest_streak": user.highest_streak,
            "major": student_profile.major if student_profile else "",
            "current_status": student_profile.current_status if student_profile else "",
        }
    )
