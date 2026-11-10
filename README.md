# LearnHub

A Django REST API backend with JWT authentication, Stripe Checkout payments, background processing, file uploads, and health monitoring. Built with Django REST Framework, PostgreSQL, Celery, RabbitMQ, Redis, and Docker Compose.

LearnHub is a backend engineering portfolio project. It focuses on production-minded concerns such as payment reliability, background jobs, upload validation, and dependency health checks.

## Highlights

- **Reliable Stripe webhooks:** signature verification, event-ID tracking to ignore duplicate deliveries, database transactions with row locking on the order, and validation of the paid amount and currency against the stored order.
- **Background processing:** Celery workers with RabbitMQ as the broker. Creating a task enqueues a notification job, and enqueue failures are logged.
- **Safe file uploads:** PDF, JPEG, and PNG only, with extension and file-signature validation and a 5 MB limit.
- **Ownership-based access:** tasks, attachments, and notifications are only visible to their owners.
- **Health endpoints:** separate liveness and readiness checks (PostgreSQL and Redis), returning `503` when a dependency is down.
- **Query optimization:** `prefetch_related()` on posts and their comments.

## Tech Stack

| Category | Technology |
|---|---|
| Language | Python |
| Framework | Django, Django REST Framework |
| Authentication | Simple JWT |
| Database | PostgreSQL 17 |
| Background jobs | Celery, RabbitMQ 3.13 |
| Cache and health checks | Redis 7 |
| Payments | Stripe Checkout (test mode) |
| Query layer | Graphene-Django (GraphQL) |
| Containers | Docker, Docker Compose |

## Architecture

```text
                 API client
                     |
                     v
             Django REST API
                     |
     +---------------+----------------+
     |               |                |
  Accounts         Tasks           Payments
                     |                |
                     v                v
               Notifications        Stripe
                     |
                     v
                PostgreSQL

  Celery worker  <--  RabbitMQ  <--  Django API
  Redis: caching and readiness checks
```

## Project Structure

```text
learnhub/
├── learnhub/            # project settings, urls, asgi/wsgi
├── library/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── services.py
│   ├── tasks.py
│   └── tests.py
├── requirements/
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quick Start

Requires Git, Docker, and Docker Compose V2.

```bash
git clone https://github.com/SOLAIY96/learnhub.git
cd learnhub
cp .env.example .env
docker compose up --build -d
docker compose exec web python manage.py migrate
```

| Service | Address |
|---|---|
| API | http://localhost:8000 |
| Django admin | http://localhost:8000/admin/ |
| RabbitMQ management | http://localhost:15672 |

Run the tests:

```bash
docker compose exec web python manage.py test
```

## Environment Variables

Copy `.env.example` to `.env` and fill in the values. Never commit a real `.env` file.

| Variable | Description |
|---|---|
| `DEBUG` | Enables or disables Django debug mode |
| `SECRET_KEY` | Django signing key |
| `DATABASE_URL` | PostgreSQL connection string (use the Compose service name `db` as the host) |
| `FRONTEND_URL` | Frontend URL used for Stripe redirects |
| `STRIPE_SECRET_KEY` | Stripe test-mode secret key (`sk_test_...`) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (`whsec_...`) |

## API Reference

Authentication uses JWT. Send the access token as `Authorization: Bearer <token>`.

### Authentication

| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/register/` | Register a user | Public |
| POST | `/token/` | Obtain access and refresh tokens | Public |
| POST | `/token/refresh/` | Refresh the access token | Public |
| POST | `/change-password/` | Change password | Authenticated |

### Tasks

| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET, POST | `/tasks/` | List own tasks, create a task | Authenticated |
| GET, PUT, PATCH, DELETE | `/tasks/{id}/` | Retrieve, update, delete a task | Owner |

### Posts

| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/posts/?search=django` | List posts with comments, search by title | Authenticated |

### Attachments

| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET, POST | `/attachments/` | List own files, upload a file (PDF, JPEG, PNG, max 5 MB) | Authenticated |

### Payments

| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/payments/checkout/` | Create a Stripe Checkout session | Authenticated |
| GET | `/payments/checkout/status/` | Get payment order status | Authenticated |
| POST | `/payments/webhook/` | Receive Stripe webhook events | Stripe signature |

### Notifications

| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/notifications/` | List notifications, newest first | Authenticated |
| GET, PATCH | `/notifications/{id}/` | Retrieve a notification, mark it as read | Owner |
| GET | `/notifications/unread-count/` | Get the unread count | Authenticated |

### Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health/live/` | Liveness: the app is running |
| GET | `/health/ready/` | Readiness: PostgreSQL and Redis are reachable (`200` or `503`) |

### GraphQL

A GraphQL endpoint is available at `/graphql/` through Graphene-Django.

## How Payments Work

1. An authenticated user requests a checkout session.
2. The API creates a pending order and a Stripe Checkout session.
3. The user pays on Stripe's hosted page.
4. Stripe sends a webhook to `/payments/webhook/`.
5. The API verifies the signature and checks that the event has not been processed before.
6. Inside a transaction, the order row is locked, and the amount and currency are checked against the stored order.
7. The order is marked as paid, a payment-success notification is created, and the event ID is recorded.

The current checkout is a fixed USD 10.00 test purchase and only accepts Stripe test-mode keys.

To test webhooks locally, forward Stripe events with the Stripe CLI:

```bash
stripe listen --forward-to localhost:8000/payments/webhook/
```

## Useful Commands

```bash
docker compose ps                                   # running containers
docker compose logs -f web celery_worker            # follow logs
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py showmigrations
docker compose down                                 # stop, keep data
docker compose down -v                              # stop and delete database volumes
```

## Roadmap

- [ ] OpenAPI / Swagger documentation
- [ ] GitHub Actions CI running the test suite
- [ ] Wider unit and integration test coverage
- [ ] Celery retry and failure handling
- [ ] Structured logging
- [ ] Production deployment configuration
- [ ] Payments beyond the fixed test checkout

## Author

Built by [SOLAIY96](https://github.com/SOLAIY96) with Python and Django.
