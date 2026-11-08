import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.filters import SearchFilter
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from stripe import StripeError

from .models import (
    Attachment,
    Notification,
    Order,
    Post,
    StripeWebhookEvent,
    Task,
)
from .serializers import (
    AttachmentSerializer,
    ChangePasswordSerializer,
    NotificationSerializer,
    PostSerializer,
    RegisterSerializer,
    TaskSerializer,
)
from .services import create_notification
from .tasks import send_task_notification

logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class PostListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["title"]
    queryset = Post.objects.prefetch_related("comments")
    serializer_class = PostSerializer


class TaskListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskSerializer

    def get_queryset(self):
        return (
            Task.objects
            .select_related("owner")
            .filter(owner=self.request.user)
        )

    def perform_create(self, serializer):
        task = serializer.save(owner=self.request.user)

        create_notification(
            recipient=self.request.user,
            message=(
                f'Your task "{task.title}" was created.'
            ),
        )

        logger.info(
            "Task created",
            extra={
                "task_id": task.id,
                "user_id": self.request.user.id,
            },
        )

        try:
            send_task_notification.delay(task.id)
        except Exception:
            logger.exception(
                "Task notification enqueue failed",
                extra={
                    "task_id": task.id,
                    "user_id": self.request.user.id,
                },
            )


class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.filter(owner=self.request.user)

    def perform_update(self, serializer):
        task = serializer.save()

        logger.info(
            "Task updated",
            extra={
                "task_id": task.id,
                "user_id": self.request.user.id,
            },
        )

    def perform_destroy(self, instance):
        task_id = instance.id
        instance.delete()

        logger.info(
            "Task deleted",
            extra={
                "task_id": task_id,
                "user_id": self.request.user.id,
            },
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)

        if serializer.is_valid():
            user = request.user

            if not user.check_password(
                serializer.validated_data["old_password"]
            ):
                logger.warning(
                    "Password change failed: incorrect old password",
                    extra={"user_id": user.id},
                )

                return Response(
                    {"old_password": ["wrong password."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.set_password(serializer.validated_data["new_password"])
            user.save()

            return Response(
                {"message": "password change successfully."},
                status=status.HTTP_200_OK,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class AttachmentListCreateView(generics.ListCreateAPIView):
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return (
            Attachment.objects
            .filter(owner=self.request.user)
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@csrf_exempt
def stripe_webhook(request):
    """Verify Stripe events and update orders idempotently."""
    if request.method != "POST":
        return HttpResponse(status=405)

    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

    if not webhook_secret:
        logger.error("Stripe webhook secret is not configured")
        return HttpResponse(status=500)

    signature = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(
            request.body,
            signature,
            webhook_secret,
        )
    except (ValueError, stripe.SignatureVerificationError):
        logger.warning("Invalid Stripe webhook payload or signature")
        return HttpResponse(status=400)

    event_id = event.get("id")
    event_type = event.get("type")

    if not event_id or not event_type:
        logger.warning("Stripe webhook is missing its event ID or type")
        return HttpResponse(status=400)

    supported_events = {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }

    if event_type not in supported_events:
        return HttpResponse(status=200)

    session = event["data"]["object"]
    session_id = session.get("id")

    if not session_id:
        logger.warning("Stripe Checkout event is missing its session ID")
        return HttpResponse(status=400)

    try:
        with transaction.atomic():
            if StripeWebhookEvent.objects.filter(event_id=event_id).exists():
                return HttpResponse(status=200)

            order = Order.objects.select_for_update().get(
                provider_session_id=session_id,
            )

            # Recheck after acquiring the order lock.
            if StripeWebhookEvent.objects.filter(event_id=event_id).exists():
                return HttpResponse(status=200)

            if session.get("payment_status") != "paid":
                logger.info(
                    "Stripe session is not paid: order_id=%s",
                    order.pk,
                )

                StripeWebhookEvent.objects.create(
                    event_id=event_id,
                    event_type=event_type,
                )

                return HttpResponse(status=200)

            if order.currency.upper() != "USD":
                logger.error(
                    "Unsupported payment currency: order_id=%s",
                    order.pk,
                )
                return HttpResponse(status=400)

            expected_amount = int(order.amount * 100)
            actual_amount = session.get("amount_total")
            actual_currency = session.get("currency", "").upper()

            if (
                actual_amount != expected_amount
                or actual_currency != order.currency.upper()
            ):
                logger.error(
                    "Stripe payment mismatch: order_id=%s",
                    order.pk,
                )
                return HttpResponse(status=400)

            if order.status != Order.Status.PENDING:
                logger.warning(
                    "Ignoring payment event for non-pending order: "
                    "order_id=%s status=%s",
                    order.pk,
                    order.status,
                )

                StripeWebhookEvent.objects.create(
                    event_id=event_id,
                    event_type=event_type,
                )

                return HttpResponse(status=200)

            order.status = Order.Status.PAID
            order.save(update_fields=["status"])

            create_notification(
                recipient=order.user,
                message=(
                    f"Payment successful! Order #{order.pk} "
                    f"for {order.currency.upper()} {order.amount} "
                    "has been paid."
                ),
            )

            StripeWebhookEvent.objects.create(
                event_id=event_id,
                event_type=event_type,
            )

            logger.info(
                "Stripe payment verified: order_id=%s event_id=%s",
                order.pk,
                event_id,
            )

    except Order.DoesNotExist:
        logger.error(
            "No order found for Stripe session_id=%s",
            session_id,
        )
        return HttpResponse(status=400)

    return HttpResponse(status=200)


class CheckoutSessionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    # Fixed server-controlled test purchase: USD 10.00.
    ORDER_AMOUNT = Decimal("10.00")
    CURRENCY = "usd"
    STRIPE_UNIT_AMOUNT = 1000  # USD 10.00 = 1,000 cents

    def post(self, request):
        secret_key = getattr(settings, "STRIPE_SECRET_KEY", "")

        if not secret_key:
            return Response(
                {"error": "Stripe is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not secret_key.startswith("sk_test_"):
            return Response(
                {"error": "Checkout is restricted to Stripe test mode."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        order = Order.objects.create(
            user=request.user,
            amount=self.ORDER_AMOUNT,
            currency=self.CURRENCY.upper(),
            status=Order.Status.PENDING,
        )

        try:
            stripe.api_key = secret_key

            session = stripe.checkout.Session.create(
                mode="payment",
                line_items=[
                    {
                        "price_data": {
                            "currency": self.CURRENCY,
                            "unit_amount": self.STRIPE_UNIT_AMOUNT,
                            "product_data": {
                                "name": "Test purchase",
                                "description": "Day 4 Stripe integration test",
                            },
                        },
                        "quantity": 1,
                    }
                ],
                metadata={"order_id": str(order.pk)},
                payment_intent_data={"metadata": {"order_id": str(order.pk)}},
                success_url=(
                    f"{settings.FRONTEND_URL}/?checkout=success"
                    "&session_id={CHECKOUT_SESSION_ID}"
                ),
                cancel_url=(f"{settings.FRONTEND_URL}/?checkout=cancelled"),
            )

            order.provider_session_id = session.id
            order.save(update_fields=["provider_session_id"])

            return Response(
                {
                    "order_id": order.pk,
                    "checkout_url": session.url,
                },
                status=status.HTTP_201_CREATED,
            )

        except StripeError:
            logger.exception("Stripe Checkout session creation failed")

            order.status = Order.Status.FAILED
            order.save(update_fields=["status"])

            return Response(
                {"error": ("Unable to create the Stripe checkout session.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class CheckoutStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session_id = request.query_params.get("session_id", "").strip()

        if not session_id:
            return Response(
                {"error": "session_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = Order.objects.get(
                provider_session_id=session_id,
                user=request.user,
            )

        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "order_id": order.pk,
                "status": order.status,
                "amount": str(order.amount),
                "currency": order.currency,
            },
            status=status.HTTP_200_OK,
        )


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class NotificationDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class UnreadNotificationCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        unread_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).count()

        return Response({"unread_count": unread_count})
