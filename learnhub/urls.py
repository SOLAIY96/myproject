"""
URL configuration for learnhub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

import logging

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from graphene_django.views import GraphQLView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from library.views import (
    AttachmentListCreateView,
    ChangePasswordView,
    CheckoutSessionCreateView,
    CheckoutStatusView,
    NotificationDetailView,
    NotificationListView,
    PostListView,
    RegisterView,
    TaskDetailView,
    TaskListCreateView,
    UnreadNotificationCountView,
    stripe_webhook,
)

logger = logging.getLogger(__name__)


def health_live(request):
    logger.info(
        "event=health_check endpoint=%s status=%s",
        request.path,
        200,
    )

    return JsonResponse({"status": "alive"})


def health_ready(request):
    checks = {
        "database": False,
        "redis": False,
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = True
    except Exception:
        logger.exception(
            "event=health_check_failed dependency=database endpoint=%s",
            request.path,
        )

    try:
        cache.set("health_check", "ok", timeout=10)
        checks["redis"] = cache.get("health_check") == "ok"
    except Exception:
        logger.exception(
            "event=health_check_failed dependency=redis endpoint=%s",
            request.path,
        )

    ready = all(checks.values())

    return JsonResponse(
        {
            "status": "ready" if ready else "not_ready",
            "checks": checks,
        },
        status=200 if ready else 503,
    )


def debug_failure(request):
    logger.error("event=debug_failure message=Intentional test failure")
    raise Exception("Intentional Day 5 debugging failure")


urlpatterns = [
    path("health/live/", health_live, name="health-live"),
    path("health/ready/", health_ready, name="health-ready"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("admin/", admin.site.urls),
    path("register/", RegisterView.as_view(), name="register"),
    path("posts/", PostListView.as_view()),
    path("tasks/", TaskListCreateView.as_view(), name="task-list"),
    path("tasks/<int:pk>/", TaskDetailView.as_view(), name="task-detail"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path(
        "attachments/",
        AttachmentListCreateView.as_view(),
        name="attachment-list",
    ),
    path(
        "payments/checkout/",
        CheckoutSessionCreateView.as_view(),
        name="stripe-checkout",
    ),
    path(
        "payments/checkout/status/",
        CheckoutStatusView.as_view(),
        name="stripe-checkout-status",
    ),
    path(
        "payments/webhook/",
        stripe_webhook,
        name="stripe-webhook",
    ),
    path(
        "notifications/",
        NotificationListView.as_view(),
        name="notification-list",
    ),
    path(
        "notifications/unread-count/",
        UnreadNotificationCountView.as_view(),
        name="notification-unread-count",
    ),
    path(
        "notifications/<int:pk>/",
        NotificationDetailView.as_view(),
        name="notification-detail",
    ),
    path("graphql/", GraphQLView.as_view(graphiql=True)),
]


if settings.DEBUG:
    urlpatterns += [
        path("debug/failure/", debug_failure, name="debug-failure"),
        path("__debug__/", include("debug_toolbar.urls")),
    ]

    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
