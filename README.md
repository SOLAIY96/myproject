# LearnHub

[![Django CI](https://github.com/SOLAIY96/learnhub/actions/workflows/django.yml/badge.svg)](https://github.com/SOLAIY96/learnhub/actions/workflows/django.yml)

A Django REST API with JWT authentication, Stripe Checkout payments, file uploads, notifications, and health checks, plus a small React client to exercise it. It runs on PostgreSQL, Redis, Celery, and RabbitMQ with Docker Compose.

The focus is production-minded backend work: payment reliability, upload validation, ownership-based access control, observability, and CI.

## Highlights

- **Reliable Stripe webhooks.** Signature verification, a unique event ID per processed event, and a transaction that locks the order row (`select_for_update`) and rechecks for duplicates after taking the lock. The paid amount and currency are validated against the stored order, and only pending orders can move to paid.
- **Tested under concurrency.** The test suite includes a rollback test (a failed event write leaves the order untouched) and a `TransactionTestCase` that delivers the same webhook from two threads at once.
- **Safe file uploads.** PDF, JPEG, and PNG only, with extension checks, file-signature checks (a renamed file is rejected), and a 5 MB limit.
- **Ownership-based access.** Tasks, attachments, notifications, and payment status are only visible to their owner.
- **Observability.** Every response carries an `X-Request-ID`, which is also attached to log lines. Sentry is optional through `SENTRY_DSN`.
- **Health endpoints.** Liveness and readiness checks (PostgreSQL and Redis), with `503` when a dependency is down.
- **CI.** GitHub Actions runs against real PostgreSQL and Redis services: Django system check, migration drift check, tests, Black, isort, and Flake8.

## Tech Stack

| Area | Technology |
|---|---|
| Backend | Python 3.12, Django, Django REST Framework |
| App server | Gunicorn |

main
| Auth | Simple JWT (15-minute access tokens, 7-day refresh tokens) |
| Database | PostgreSQL 17 |
| Background jobs | Celery with RabbitMQ 3.13 |
| Cache and readiness checks | Redis 7 |
| Payments | Stripe Checkout (test mode) |
| Frontend | React 19, Vite |
| Tooling | Docker Compose, GitHub Actions, Black, isort, Flake8 |

## Architecture

```text
React client (Vite, :5173)
        |
        v
Django REST API (:8000) ----> Stripe Checkout
        |                          |
        |                          v
        |                  Stripe webhook --> /payments/webhook/
        |
        +--> PostgreSQL   (users, tasks, orders, notifications, webhook events)
        +--> Redis        (cache, readiness check)
        +--> RabbitMQ --> Celery worker
```

## Project Structure

```text
learnhub/
├── .github/workflows/django.yml   # CI
├── docs/cloud-architecture.md     # planned AWS layout
├── frontend/                      # React + Vite client
├── learnhub/                      # settings, urls, celery app, GraphQL schema
├── library/                       # models, serializers, views, services, tasks, middleware
│   └── tests/
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

## Getting Started

Requires Git, Docker with Compose V2, and Node.js (for the frontend).

### 1. Backend

```bash
git clone https://github.com/SOLAIY96/myproject.git
cd myproject
cp .env.example .env
```

Edit `.env`. A working local setup looks like this (use your own Stripe test keys):

```env
SECRET_KEY=change-me-to-a-long-random-string
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
FRONTEND_URL=http://localhost:5173

POSTGRES_DB=learnhub
POSTGRES_USER=learnhub
POSTGRES_PASSWORD=choose-a-local-password
POSTGRES_HOST=db
POSTGRES_PORT=5432

CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//

STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

Start everything and run migrations:

```bash
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser   # optional
```

| Service | Address |
|---|---|
| API | http://localhost:8000 |
| Django admin | http://localhost:8000/admin/ |
| GraphiQL | http://localhost:8000/graphql/ |
| RabbitMQ management | http://localhost:15672 |

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The client runs at http://localhost:5173. It supports login with automatic token refresh, tasks, notifications, attachment upload, and the Stripe checkout flow. The API address is currently set in `frontend/src/services/api.js`.

### 3. Stripe webhooks (local)

Forward Stripe events to your machine with the [Stripe CLI](https://docs.stripe.com/stripe-cli):

```bash
stripe listen --forward-to localhost:8000/payments/webhook/
```

Copy the `whsec_...` value it prints into `STRIPE_WEBHOOK_SECRET` in `.env`, then restart the `web` service.

## Running with Gunicorn

[Gunicorn](https://gunicorn.org/) is the production app server. Run it from the project root:

```bash
gunicorn learnhub.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 30
```

Inside Docker Compose:

```bash
docker compose exec web gunicorn learnhub.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Notes:

- Set `DEBUG=False` and list your real domain in `ALLOWED_HOSTS`.
- A common starting point for `--workers` is `(2 x CPU cores) + 1`.
- Gunicorn does not serve static files or user uploads. Production needs WhiteNoise, a reverse proxy such as Nginx, or object storage such as S3.
- Put the app behind HTTPS (a reverse proxy or load balancer) before using real payments.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Django signing key |
| `DEBUG` | No | Defaults to `False` |
| `ALLOWED_HOSTS` | No | Comma-separated. Defaults to `localhost,127.0.0.1` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | Yes | PostgreSQL connection. Use `db` as the host inside Docker Compose |
| `CELERY_BROKER_URL` | Yes | RabbitMQ URL |
| `REDIS_URL` | No | Defaults to `redis://redis:6379/1` |
| `STRIPE_SECRET_KEY` | Yes (except in tests and CI) | Must start with `sk_test_`. Checkout refuses any other key |
| `STRIPE_PUBLISHABLE_KEY` | No | Stripe publishable key |
| `STRIPE_WEBHOOK_SECRET` | For payments | Without it the webhook returns `500` |
| `FRONTEND_URL` | No | Used for Stripe redirects. Defaults to `http://localhost:5173` |
| `SENTRY_DSN` | No | Enables Sentry error reporting |

Never commit a real `.env` file.

## API Reference

Authenticate with `Authorization: Bearer <access_token>`. List endpoints are paginated (`?page=2`, 10 per page).

### Authentication

| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/register/` | Create an account | Public |
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
| GET | `/posts/?search=django` | List posts with their comments, search by title | Authenticated |

### Attachments

| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET, POST | `/attachments/` | List own files, upload a file (PDF, JPEG, PNG, up to 5 MB) | Authenticated |

### Payments

| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/payments/checkout/` | Create a pending order and a Stripe Checkout session | Authenticated |
| GET | `/payments/checkout/status/?session_id=...` | Get the status of your order | Authenticated |
| POST | `/payments/webhook/` | Receive Stripe events | Stripe signature |

### Notifications

| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/notifications/` | List notifications, newest first | Authenticated |
| GET, PATCH | `/notifications/{id}/` | Retrieve a notification, mark it as read | Owner |
| GET | `/notifications/unread-count/` | Get the unread count | Authenticated |

### Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health/live/` | The app is running |
| GET | `/health/ready/` | PostgreSQL and Redis are reachable (`200`, or `503` with per-dependency results) |

### GraphQL

`/graphql/` exposes a `tasks` query and a `createTask` mutation through Graphene-Django.

## How Payments Work

1. An authenticated user calls `POST /payments/checkout/`.
2. The API creates a pending order and a Stripe Checkout session, then stores the session ID on the order.
3. The user pays on Stripe's hosted page and is redirected back to `FRONTEND_URL`.
4. Stripe sends `checkout.session.completed` or `checkout.session.async_payment_succeeded` to `/payments/webhook/`.
5. The API verifies the signature and ignores event types it does not handle.
6. Inside a transaction it checks the event ID, locks the order, checks it again, and validates the payment status, currency, and amount against the stored order.
7. A pending order becomes paid, a notification is created, and the event ID is recorded. Duplicate deliveries return `200` without changing anything.

The checkout is currently a fixed USD 10.00 test purchase, and only `sk_test_` keys are accepted.

## Testing and CI

```bash
docker compose exec web python manage.py test
```

The tests cover Stripe webhooks (valid, duplicate, concurrent, invalid signature, amount and currency mismatch, unpaid, unknown, failed, and cancelled orders), attachment upload validation and ownership, and notifications.

CI (`.github/workflows/django.yml`) runs on every push and pull request. Code style is enforced with Black, isort, and Flake8:

```bash
black --check . && isort --check-only . && flake8 .
```

## Known Limitations

- The Celery notification task enqueued when a task is created is a placeholder that only logs a message.
- The GraphQL endpoint uses Django session authentication, not JWT.
- Default API throttling is strict (3 requests per minute for anonymous users, 5 for authenticated users). See `REST_FRAMEWORK` in `learnhub/settings.py`.
- Uploaded files are only served by Django when `DEBUG=True`, and Gunicorn does not serve static files or uploads. A production deployment needs WhiteNoise or a reverse proxy for static files, plus file storage for uploads. `docs/cloud-architecture.md` describes the planned AWS layout.

## Roadmap

- [ ] OpenAPI / Swagger documentation
- [ ] Real background jobs (for example, expiring stale pending orders) with retries
- [ ] Handle `async_payment_failed` and `checkout.session.expired` events
- [ ] Production deployment configuration and a live demo
- [ ] API tests for tasks, authentication, and the checkout view

## Author


Edit `.env`. A working local setup looks like this (use your own Stripe test keys):

```env
SECRET_KEY=change-me-to-a-long-random-string
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
FRONTEND_URL=http://localhost:5173

POSTGRES_DB=learnhub
POSTGRES_USER=learnhub
POSTGRES_PASSWORD=choose-a-local-password
POSTGRES_HOST=db
POSTGRES_PORT=5432

CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//

STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

Start everything and run migrations:

```bash
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser   # optional
```

| Service | Address |
|---|---|
| API | http://localhost:8000 |
| Django admin | http://localhost:8000/admin/ |
| GraphiQL | http://localhost:8000/graphql/ |
| RabbitMQ management | http://localhost:15672 |

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The client runs at http://localhost:5173. It supports login with automatic token refresh, tasks, notifications, attachment upload, and the Stripe checkout flow. The API address is currently set in `frontend/src/services/api.js`.

### 3. Stripe webhooks (local)

Forward Stripe events to your machine with the [Stripe CLI](https://docs.stripe.com/stripe-cli):

```bash
stripe listen --forward-to localhost:8000/payments/webhook/
```

Copy the `whsec_...` value it prints into `STRIPE_WEBHOOK_SECRET` in `.env`, then restart the `web` service.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Django signing key |
| `DEBUG` | No | Defaults to `False` |
| `ALLOWED_HOSTS` | No | Comma-separated. Defaults to `localhost,127.0.0.1` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | Yes | PostgreSQL connection. Use `db` as the host inside Docker Compose |
| `CELERY_BROKER_URL` | Yes | RabbitMQ URL |
| `REDIS_URL` | No | Defaults to `redis://redis:6379/1` |
| `STRIPE_SECRET_KEY` | Yes (except in tests and CI) | Must start with `sk_test_`. Checkout refuses any other key |
| `STRIPE_PUBLISHABLE_KEY` | No | Stripe publishable key |
| `STRIPE_WEBHOOK_SECRET` | For payments | Without it the webhook returns `500` |
| `FRONTEND_URL` | No | Used for Stripe redirects. Defaults to `http://localhost:5173` |
| `SENTRY_DSN` | No | Enables Sentry error reporting |

Never commit a real `.env` file.

## API Reference

Authenticate with `Authorization: Bearer <access_token>`. List endpoints are paginated (`?page=2`, 10 per page).

### Authentication

| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/register/` | Create an account | Public |
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
| GET | `/posts/?search=django` | List posts with their comments, search by title | Authenticated |

### Attachments

| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET, POST | `/attachments/` | List own files, upload a file (PDF, JPEG, PNG, up to 5 MB) | Authenticated |

### Payments

| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/payments/checkout/` | Create a pending order and a Stripe Checkout session | Authenticated |
| GET | `/payments/checkout/status/?session_id=...` | Get the status of your order | Authenticated |
| POST | `/payments/webhook/` | Receive Stripe events | Stripe signature |

### Notifications

| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/notifications/` | List notifications, newest first | Authenticated |
| GET, PATCH | `/notifications/{id}/` | Retrieve a notification, mark it as read | Owner |
| GET | `/notifications/unread-count/` | Get the unread count | Authenticated |

### Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health/live/` | The app is running |
| GET | `/health/ready/` | PostgreSQL and Redis are reachable (`200`, or `503` with per-dependency results) |

### GraphQL

`/graphql/` exposes a `tasks` query and a `createTask` mutation through Graphene-Django.

## How Payments Work

1. An authenticated user calls `POST /payments/checkout/`.
2. The API creates a pending order and a Stripe Checkout session, then stores the session ID on the order.
3. The user pays on Stripe's hosted page and is redirected back to `FRONTEND_URL`.
4. Stripe sends `checkout.session.completed` or `checkout.session.async_payment_succeeded` to `/payments/webhook/`.
5. The API verifies the signature and ignores event types it does not handle.
6. Inside a transaction it checks the event ID, locks the order, checks it again, and validates the payment status, currency, and amount against the stored order.
7. A pending order becomes paid, a notification is created, and the event ID is recorded. Duplicate deliveries return `200` without changing anything.

The checkout is currently a fixed USD 10.00 test purchase, and only `sk_test_` keys are accepted.

## Testing and CI

```bash
docker compose exec web python manage.py test
```

The tests cover Stripe webhooks (valid, duplicate, concurrent, invalid signature, amount and currency mismatch, unpaid, unknown, failed, and cancelled orders), attachment upload validation and ownership, and notifications.

CI (`.github/workflows/django.yml`) runs on every push and pull request. Code style is enforced with Black, isort, and Flake8:

```bash
black --check . && isort --check-only . && flake8 .
```

## Known Limitations

- The Celery notification task enqueued when a task is created is a placeholder that only logs a message.
- The GraphQL endpoint uses Django session authentication, not JWT.
- Default API throttling is strict (3 requests per minute for anonymous users, 5 for authenticated users). See `REST_FRAMEWORK` in `learnhub/settings.py`.
- Uploaded files are only served by Django when `DEBUG=True`, and Docker runs the development server. A production deployment needs a WSGI/ASGI server and file storage. `docs/cloud-architecture.md` describes the planned AWS layout.

## Roadmap

- [ ] OpenAPI / Swagger documentation
- [ ] Real background jobs (for example, expiring stale pending orders) with retries
- [ ] Handle `async_payment_failed` and `checkout.session.expired` events
- [ ] Production deployment configuration and a live demo
- [ ] API tests for tasks, authentication, and the checkout view

## Author

main
Built by [SOLAIY96](https://github.com/SOLAIY96).
