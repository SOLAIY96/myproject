
from .models import Notification


def create_notification(*, recipient, message):
    return Notification.objects.create(
        recipient=recipient,
        message=message,
    )
