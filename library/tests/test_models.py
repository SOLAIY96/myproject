import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import patch

import stripe
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import (
    DatabaseError,
    close_old_connections,
    connection,
)
from django.test import (
    TestCase,
    TransactionTestCase,
    override_settings,
)
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from library.models import (
    Attachment,
    Comment,
    Notification,
    Order,
    Post,
    StripeWebhookEvent,
    Task,
)

User = get_user_model()


class UserModelTests(TestCase):
    def test_user_creation(self):
        user = User.objects.create_user(
            username="testuser",
            password="testpass123",
        )

        self.assertEqual(user.username, "testuser")
        self.assertTrue(user.check_password("testpass123"))


class TaskModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="taskuser",
            password="testpass123",
        )

    def test_task_creation(self):
        task = Task.objects.create(
            owner=self.user,
            title="Learn Django testing",
        )

        self.assertEqual(task.title, "Learn Django testing")
        self.assertEqual(task.owner, self.user)
        self.assertFalse(task.completed)

    def test_task_string_representation(self):
        task = Task.objects.create(
            owner=self.user,
            title="Write tests",
        )

        self.assertEqual(str(task), "Write tests")


class PostModelTests(TestCase):
    def test_post_creation(self):
        post = Post.objects.create(title="My first post")

        self.assertEqual(post.title, "My first post")
        self.assertIsNotNone(post.created_at)


class CommentModelTests(TestCase):
    def test_comment_creation(self):
        user = User.objects.create_user(
            username="commentuser",
            password="testpass123",
        )
        post = Post.objects.create(title="Test post")

        comment = Comment.objects.create(
            post=post,
            user=user,
            content="This is a test comment.",
        )

        self.assertEqual(comment.post, post)
        self.assertEqual(comment.user, user)
        self.assertEqual(comment.content, "This is a test comment.")
        self.assertIn("commentuser", str(comment))


class AttachmentUploadTests(APITestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)

        media_settings = override_settings(MEDIA_ROOT=self.temp_media.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

        self.alice = User.objects.create_user(
            username="alice",
            password="Test-password-123!",
        )
        self.bob = User.objects.create_user(
            username="bob",
            password="Test-password-456!",
        )

        self.client.force_authenticate(user=self.alice)
        self.url = "/attachments/"

    def make_pdf(self, name="report.pdf", size=100):
        content = b"%PDF-1.7\n"
        content += b"x" * max(0, size - len(content))

        return SimpleUploadedFile(
            name=name,
            content=content,
            content_type="application/pdf",
        )

    def test_authenticated_user_can_upload_pdf(self):
        response = self.client.post(
            self.url,
            {"file": self.make_pdf()},
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(Attachment.objects.count(), 1)

        attachment = Attachment.objects.get()
        self.assertEqual(attachment.owner, self.alice)
        self.assertEqual(response.data["owner"], "alice")

    def test_rejects_file_over_5_mb(self):
        response = self.client.post(
            self.url,
            {"file": self.make_pdf(size=5 * 1024 * 1024 + 1)},
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(Attachment.objects.count(), 0)

    def test_rejects_disallowed_extension(self):
        response = self.client.post(
            self.url,
            {"file": self.make_pdf(name="script.exe")},
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(Attachment.objects.count(), 0)

    def test_rejects_disallowed_content_type(self):
        upload = SimpleUploadedFile(
            name="photo.jpg",
            content=b"fake-image",
            content_type="application/octet-stream",
        )

        response = self.client.post(
            self.url,
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(Attachment.objects.count(), 0)

    def test_rejects_spoofed_pdf_contents(self):
        upload = SimpleUploadedFile(
            name="fake.pdf",
            content=b"This is not a PDF",
            content_type="application/pdf",
        )

        response = self.client.post(
            self.url,
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(Attachment.objects.count(), 0)

    def test_accepts_valid_pdf_signature(self):
        response = self.client.post(
            self.url,
            {"file": self.make_pdf()},
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(Attachment.objects.count(), 1)

    def test_user_cannot_upload_for_another_owner(self):
        response = self.client.post(
            self.url,
            {
                "file": self.make_pdf(),
                "owner": self.bob.pk,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        attachment = Attachment.objects.get()
        self.assertEqual(attachment.owner, self.alice)

    def test_list_only_returns_current_users_attachments(self):
        Attachment.objects.create(
            owner=self.alice,
            file=self.make_pdf("alice.pdf"),
        )
        Attachment.objects.create(
            owner=self.bob,
            file=self.make_pdf("bob.pdf"),
        )

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Support both paginated and unpaginated API responses.
        if isinstance(response.data, dict):
            results = response.data["results"]
        else:
            results = response.data

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["owner"], "alice")

    def test_unauthenticated_user_cannot_upload(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            self.url,
            {"file": self.make_pdf()},
            format="multipart",
        )

        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )
        self.assertEqual(Attachment.objects.count(), 0)


class NotificationAPITests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="alice",
            password="test-password-123",
        )
        self.user2 = User.objects.create_user(
            username="bob",
            password="test-password-456",
        )

        self.notification = Notification.objects.create(
            recipient=self.user1,
            message="Your task was assigned.",
        )

        self.client.force_authenticate(user=self.user1)

    def test_user_can_list_own_notifications(self):
        response = self.client.get(reverse("notification-list"))

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["message"],
            "Your task was assigned.",
        )

    def test_user_cannot_see_other_users_notifications(self):
        other_notification = Notification.objects.create(
            recipient=self.user2,
            message="Bob's private notification",
        )

        response = self.client.get(reverse("notification-list"))

        returned_ids = [item["id"] for item in response.data["results"]]

        self.assertNotIn(other_notification.id, returned_ids)

    def test_user_can_mark_notification_as_read(self):
        response = self.client.patch(
            reverse(
                "notification-detail",
                kwargs={"pk": self.notification.pk},
            ),
            {"is_read": True},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_user_cannot_update_another_users_notification(self):
        other_notification = Notification.objects.create(
            recipient=self.user2,
            message="Bob's private notification",
        )

        response = self.client.patch(
            reverse(
                "notification-detail",
                kwargs={"pk": other_notification.pk},
            ),
            {"is_read": True},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        other_notification.refresh_from_db()
        self.assertFalse(other_notification.is_read)

    def test_unread_count(self):
        Notification.objects.create(
            recipient=self.user1,
            message="Another notification",
        )
        Notification.objects.create(
            recipient=self.user2,
            message="Bob's notification",
        )

        response = self.client.get(reverse("notification-unread-count"))

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(response.data["unread_count"], 2)

    def test_unauthenticated_user_is_rejected(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse("notification-list"))

        self.assertIn(response.status_code, [401, 403])


class StripeWebhookTests(APITestCase):
    def setUp(self):
        self.webhook_url = "/payments/webhook/"
        self.webhook_secret = "whsec_test_secret"

        self.settings_override = override_settings(
            STRIPE_WEBHOOK_SECRET=self.webhook_secret
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.user = User.objects.create_user(
            username="stripe_user",
            password="Test-password-123!",
        )

        self.order = Order.objects.create(
            user=self.user,
            amount=Decimal("10.00"),
            currency="USD",
            status=Order.Status.PENDING,
            provider_session_id="cs_test_123",
        )

        self.session = {
            "id": "cs_test_123",
            "payment_status": "paid",
            "amount_total": 1000,
            "currency": "usd",
            "metadata": {"order_id": str(self.order.pk)},
        }

        self.event = {
            "id": "evt_test_123",
            "type": "checkout.session.completed",
            "data": {"object": self.session},
        }

    def post_webhook(self):
        return self.client.post(
            self.webhook_url,
            data=b'{"test": "payload"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature",
        )

    @patch("library.views.stripe.Webhook.construct_event")
    def test_valid_paid_webhook_marks_order_paid(
        self,
        mock_construct_event,
    ):
        mock_construct_event.return_value = self.event

        response = self.post_webhook()

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            Order.Status.PAID,
        )

        mock_construct_event.assert_called_once_with(
            b'{"test": "payload"}',
            "test_signature",
            self.webhook_secret,
        )

    @patch("library.views.stripe.Webhook.construct_event")
    def test_invalid_signature_does_not_mark_order_paid(
        self,
        mock_construct_event,
    ):
        mock_construct_event.side_effect = stripe.SignatureVerificationError(
            "Invalid signature",
            "invalid_signature",
        )

        response = self.post_webhook()

        self.assertEqual(response.status_code, 400)

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            Order.Status.PENDING,
        )

    @patch("library.views.stripe.Webhook.construct_event")
    def test_duplicate_paid_event_is_safe(
        self,
        mock_construct_event,
    ):
        mock_construct_event.return_value = self.event

        first_response = self.post_webhook()
        second_response = self.post_webhook()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            Order.Status.PAID,
        )

        self.assertEqual(Order.objects.count(), 1)

        # The same Stripe event should be recorded exactly once.
        self.assertEqual(
            StripeWebhookEvent.objects.filter(event_id="evt_test_123").count(),
            1,
        )

        self.assertEqual(Order.objects.count(), 1)

    @patch("library.views.StripeWebhookEvent.objects.create")
    @patch("library.views.stripe.Webhook.construct_event")
    def test_event_record_failure_rolls_back_order_update(
        self,
        mock_construct_event,
        mock_event_create,
    ):
        mock_construct_event.return_value = self.event

        mock_event_create.side_effect = DatabaseError(
            "Simulated database failure"
        )

        with self.assertRaises(DatabaseError):
            self.post_webhook()

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.PENDING,
        )

        self.assertFalse(
            StripeWebhookEvent.objects.filter(event_id="evt_test_123").exists()
        )

    @patch("library.views.stripe.Webhook.construct_event")
    def test_amount_mismatch_does_not_mark_order_paid(
        self,
        mock_construct_event,
    ):
        bad_session = {
            **self.session,
            "amount_total": 999,
        }

        mock_construct_event.return_value = {
            **self.event,
            "data": {"object": bad_session},
        }

        response = self.post_webhook()

        self.assertEqual(response.status_code, 400)

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            Order.Status.PENDING,
        )

    @patch("library.views.stripe.Webhook.construct_event")
    def test_currency_mismatch_does_not_mark_order_paid(
        self,
        mock_construct_event,
    ):
        bad_session = {
            **self.session,
            "currency": "eur",
        }

        mock_construct_event.return_value = {
            **self.event,
            "data": {"object": bad_session},
        }

        response = self.post_webhook()

        self.assertEqual(response.status_code, 400)

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            Order.Status.PENDING,
        )

    @patch("library.views.stripe.Webhook.construct_event")
    def test_unpaid_session_does_not_mark_order_paid(
        self,
        mock_construct_event,
    ):
        unpaid_session = {
            **self.session,
            "payment_status": "unpaid",
        }

        mock_construct_event.return_value = {
            **self.event,
            "data": {"object": unpaid_session},
        }

        response = self.post_webhook()

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            Order.Status.PENDING,
        )

    @patch("library.views.stripe.Webhook.construct_event")
    def test_unknown_session_does_not_update_order(
        self,
        mock_construct_event,
    ):
        unknown_session = {
            **self.session,
            "id": "cs_test_unknown",
        }

        mock_construct_event.return_value = {
            **self.event,
            "data": {"object": unknown_session},
        }

        response = self.post_webhook()

        self.assertEqual(response.status_code, 400)

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            Order.Status.PENDING,
        )

    @patch("library.views.stripe.Webhook.construct_event")
    def test_failed_order_cannot_be_marked_paid(
        self,
        mock_construct_event,
    ):
        self.order.status = Order.Status.FAILED
        self.order.save(update_fields=["status"])

        mock_construct_event.return_value = self.event
        response = self.post_webhook()

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            Order.Status.FAILED,
        )

    @patch("library.views.stripe.Webhook.construct_event")
    def test_cancelled_order_cannot_be_marked_paid(
        self,
        mock_construct_event,
    ):
        self.order.status = Order.Status.CANCELLED
        self.order.save(update_fields=["status"])

        mock_construct_event.return_value = self.event
        response = self.post_webhook()

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            Order.Status.CANCELLED,
        )


class StripeWebhookConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("This concurrency test requires PostgreSQL.")

        self.webhook_url = "/payments/webhook/"
        self.webhook_secret = "whsec_test_secret"

        self.settings_override = override_settings(
            STRIPE_WEBHOOK_SECRET=self.webhook_secret
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.user = User.objects.create_user(
            username="stripe_concurrent_user",
            password="Test-password-123!",
        )

        self.order = Order.objects.create(
            user=self.user,
            amount=Decimal("10.00"),
            currency="USD",
            status=Order.Status.PENDING,
            provider_session_id="cs_test_concurrent",
        )

        self.event = {
            "id": "evt_test_concurrent",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_concurrent",
                    "payment_status": "paid",
                    "amount_total": 1000,
                    "currency": "usd",
                }
            },
        }

    @patch("library.views.stripe.Webhook.construct_event")
    def test_concurrent_duplicate_delivery_is_safe(
        self,
        mock_construct_event,
    ):
        mock_construct_event.return_value = self.event

        barrier = threading.Barrier(2)

        def send_webhook():
            close_old_connections()

            try:
                client = APIClient()
                barrier.wait(timeout=10)

                response = client.post(
                    self.webhook_url,
                    data=b'{"test": "payload"}',
                    content_type="application/json",
                    HTTP_STRIPE_SIGNATURE="test_signature",
                )

                return response.status_code

            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(send_webhook) for _ in range(2)]

            statuses = [future.result(timeout=30) for future in futures]

        self.assertEqual(statuses, [200, 200])

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            Order.Status.PAID,
        )

        self.assertEqual(
            StripeWebhookEvent.objects.filter(
                event_id="evt_test_concurrent"
            ).count(),
            1,
        )
