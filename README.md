LearnHub — Django REST API Backend
A feature-rich Django REST API backend built with Django REST Framework, PostgreSQL, Docker, Celery, RabbitMQ, and Redis.

LearnHub is a backend engineering portfolio project focused on practical application development and production-oriented backend concepts, including authentication, task management, payment integration, file uploads, notifications, background processing, database optimization, and application health monitoring.

Table of Contents
Features
Technology Stack
Architecture
Project Structure
Getting Started
Environment Variables
Running with Docker
Database Management
API Documentation
Authentication
Background Processing
Payment Integration
File Uploads
Health Monitoring
Testing
Logging
Future Improvements
Features
1. Authentication and User Management
User registration.
JWT authentication using Django REST Framework Simple JWT.
Access and refresh token endpoints.
Authenticated API access.
Password change functionality.
User-specific resource access.
2. Task Management
Create, retrieve, update, and delete tasks.
Associate tasks with authenticated users.
Restrict task access to their respective owners.
Validate task titles.
Automatically create notifications when tasks are created.
Trigger background notification processing through Celery.
Log important task operations.
3. Posts and Comments
Retrieve posts.
Search posts by title.
Associate comments with posts and users.
Retrieve related comments alongside posts.
Optimize related-object retrieval using prefetch_related().
4. File Uploads
Authenticated file uploads.
Associate uploaded files with their owners.
Support PDF, JPEG, and PNG files.
Validate file signatures.
Enforce a maximum upload size of 5 MB.
Handle multipart form submissions.
5. Stripe Payment Integration
Create Stripe Checkout sessions.
Create and track payment orders.
Process Stripe webhook events.
Verify webhook signatures.
Validate payment amounts and currencies.
Handle duplicate webhook deliveries using event IDs.
Update order statuses after successful payments.
Provide authenticated payment status retrieval.
Generate payment-success notifications.
Payment configuration: The current implementation uses a fixed USD 10.00 test purchase and restricts checkout to Stripe test-mode secret keys.

6. Notification System
Automatically create notifications for task creation.
Generate payment-success notifications.
Retrieve user-specific notifications.
Mark notifications as read.
Retrieve unread notification counts.
Order notifications by creation date.
7. Background Processing
Celery worker integration.
RabbitMQ message broker.
Background task execution.
Logging for background task enqueue failures.
Redis integration for caching and health checks.
8. Application Monitoring
Application liveness endpoint.
Application readiness endpoint.
PostgreSQL connectivity checks.
Redis connectivity checks.
Application logging.
Error logging for important operations.
Technology Stack

Category	Technology
Programming Language	Python
Backend Framework	Django
API Framework	Django REST Framework
Authentication	Simple JWT
Database	PostgreSQL 17
Background Processing	Celery
Message Broker	RabbitMQ 3.13
Cache	Redis 7
Payment Integration	Stripe
Containerization	Docker
Container Orchestration	Docker Compose
API Query Layer	Graphene-Django / GraphQL
Architecture
LearnHub follows a Django-based backend architecture with separate responsibilities for API handling, data persistence, background processing, and external payment integration.

High-Level Architecture

text
                   API CLIENT
                       |
                       v
                DJANGO REST API
                       |
          +------------+------------+
          |            |            |
          v            v            v
       Accounts      Tasks       Payments
          |            |            |
          |            v            v
          |       Notifications   Stripe
          |            |
          +------------+
                       |
                       v
                  PostgreSQL


             BACKGROUND PROCESSING
                       |
                       v
                     Celery
                       |
                       v
                    RabbitMQ


               INFRASTRUCTURE
                       |
                       v
                     Redis
Architecture Overview
Django: Handles HTTP requests, API endpoints, authentication, and application logic.
Django REST Framework: Provides serializers, API views, request validation, and permissions.
PostgreSQL: Stores persistent application data.
Celery: Handles asynchronous background tasks.
RabbitMQ: Acts as the message broker for background task processing.
Redis: Provides caching infrastructure and supports application readiness checks.
Stripe: Handles test-mode payment checkout and webhook events.
Docker Compose: Manages the application's containerized services.
Project Structure
The application uses Django models, serializers, views, services, and background tasks to organize backend functionality.

Example structure:


text
learnhub/
│
├── learnhub/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── library/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── services.py
│   ├── tasks.py
│   └── tests.py
│
├── requirements/
│
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
The structure above illustrates the main project components. Adjust it to match the actual repository layout.

Getting Started
Prerequisites
Install the following:

Git
Docker
Docker Compose V2
Verify the installations:


bash
docker --version
docker compose version
git --version
Clone the Repository

bash
git clone (https://github.com/SOLAIY96/myproject.git)

cd myproject
Configure Environment Variables
Create a local .env file:


bash
cp .env.example .env
Configure the required variables according to your Django settings and Docker Compose configuration.

Environment Variables
The application uses environment variables for Django configuration, database connectivity, frontend redirects, and Stripe integration.

Example .env.example:


env
DEBUG=True
SECRET_KEY=replace-with-a-local-development-secret

DATABASE_URL=postgresql://myprojectuser:myprojectpassword@db:5432/myprojectdb

FRONTEND_URL=http://localhost:3000

STRIPE_SECRET_KEY=sk_test_replace_me
STRIPE_WEBHOOK_SECRET=whsec_replace_me

Variable	Description
DEBUG	Enables or disables Django debug mode
SECRET_KEY	Django cryptographic signing key
DATABASE_URL	PostgreSQL connection string
FRONTEND_URL	Frontend URL used for Stripe redirects
STRIPE_SECRET_KEY	Stripe test-mode secret key
STRIPE_WEBHOOK_SECRET	Stripe webhook signing secret
Additional Celery and Redis variables should be documented if they are required by the actual project configuration.

Security considerations:

Never commit real .env files.
Never expose production credentials or API secrets.
Use separate environment configurations for development and production.
Use Docker Compose service names for internal container communication. For example, the database hostname is typically db, not localhost.
Keep .env.example populated with placeholders rather than real secrets.
Running with Docker
Build and Start Services

bash
docker compose up --build
To run services in detached mode:


bash
docker compose up --build -d
Apply Database Migrations

bash
docker compose exec web python manage.py migrate
Check Running Containers

bash
docker compose ps
Access the Application

Service	Address
Django API	http://localhost:8000
Django Admin	http://localhost:8000/admin/
RabbitMQ Management	http://localhost:15672
RabbitMQ management credentials depend on the Docker Compose configuration.

View Logs
View logs for all services:


bash
docker compose logs -f
View logs for individual services:


bash
docker compose logs -f web
docker compose logs -f celery_worker
docker compose logs -f db
docker compose logs -f rabbitmq
docker compose logs -f redis
Stop Services

bash
docker compose down
This stops and removes the containers and Compose network while preserving named volumes.

To remove containers and volumes:


bash
docker compose down -v
Warning: Removing volumes can permanently delete locally stored PostgreSQL data.

Database Management
Run Django management commands inside the application container.

Create Migrations

bash
docker compose exec web python manage.py makemigrations
Apply Migrations

bash
docker compose exec web python manage.py migrate
Check Migration Status

bash
docker compose exec web python manage.py showmigrations
API Documentation
The following endpoints are defined in the current URL configuration.

All paths below are relative to the application root.

Authentication

Method	Endpoint	Description	Access
POST	/register/	Register a new user	Public
POST	/token/	Obtain JWT tokens	Public
POST	/token/refresh/	Refresh access token	Public
POST	/change-password/	Change account password	Authenticated
Tasks

Method	Endpoint	Description	Access
GET	/tasks/	List user's tasks	Authenticated
POST	/tasks/	Create a task	Authenticated
GET	/tasks/{id}/	Retrieve a task	Owner
PUT/PATCH	/tasks/{id}/	Update a task	Owner
DELETE	/tasks/{id}/	Delete a task	Owner
Posts

Method	Endpoint	Description	Access
GET	/posts/	Retrieve posts	Authenticated
Search posts by title:


http
GET /posts/?search=django
Attachments

Method	Endpoint	Description	Access
GET	/attachments/	List user's attachments	Authenticated
POST	/attachments/	Upload an attachment	Authenticated
Supported formats: PDF, JPEG, PNG.

Maximum file size: 5 MB.

Payments

Method	Endpoint	Description	Access
POST	/payments/checkout/	Create Stripe Checkout session	Authenticated
GET	/payments/checkout/status/	Retrieve payment order status	Authenticated
POST	/payments/webhook/	Process Stripe webhook	Stripe signature verification
Notifications

Method	Endpoint	Description	Access
GET	/notifications/	List notifications	Authenticated
GET	/notifications/{id}/	Retrieve notification	Owner
PATCH	/notifications/{id}/	Update notification read status	Owner
GET	/notifications/unread-count/	Retrieve unread count	Authenticated
Health Monitoring

Method	Endpoint	Description
GET	/health/live/	Application liveness
GET	/health/ready/	Database and Redis readiness
GraphQL
The project also configures a GraphQL endpoint through Graphene-Django.


http
GET /graphql/
POST /graphql/
GraphQL schema and available operations depend on the configured application schema.

Authentication
The API uses JSON Web Tokens through Django REST Framework Simple JWT.

Obtain Tokens

http
POST /token/
Content-Type: application/json
Example request:


json
{
    "username": "your_username",
    "password": "your_password"
}
Use the returned access token in authenticated requests:


http
Authorization: Bearer YOUR_ACCESS_TOKEN
Refresh Token

http
POST /token/refresh/
Content-Type: application/json
Example request:


json
{
    "refresh": "YOUR_REFRESH_TOKEN"
}
Background Processing
Celery is integrated for asynchronous task processing.

RabbitMQ acts as the message broker, allowing the application to enqueue background tasks for execution by a Celery worker.

For example, creating a task triggers a notification-related Celery task.

The application also records errors when background task enqueueing fails.

Payment Integration
LearnHub integrates Stripe Checkout for test-mode payment processing.

Payment Workflow
An authenticated user requests a checkout session.
The application creates a pending order.
A Stripe Checkout session is created.
The user completes payment through Stripe Checkout.
Stripe sends a webhook event.
The application verifies the webhook signature.
Payment amount and currency are checked against the stored order.
The order status is updated.
A payment-success notification is created.
The webhook event is recorded to prevent duplicate processing.
Payment Reliability
The webhook implementation includes:

Stripe signature verification.
Event ID tracking.
Database transactions.
Order row locking.
Payment amount validation.
Currency validation.
Duplicate event handling.
The current checkout implementation supports a fixed USD 10.00 test purchase.

File Uploads
Authenticated users can upload files through the attachments endpoint.

Supported Formats
PDF
JPEG
PNG
Validation
Maximum file size of 5 MB.
File extension validation.
File signature validation.
Ownership association.
Uploads are handled using Django REST Framework's multipart request parsers.

Health Monitoring
The application provides two health endpoints.

Liveness Check

http
GET /health/live/
Returns a response indicating that the Django application is running.

Example:


json
{
    "status": "alive"
}
Readiness Check

http
GET /health/ready/
Checks:

PostgreSQL connectivity.
Redis connectivity.
Example successful response:


json
{
    "status": "ready",
    "checks": {
        "database": true,
        "redis": true
    }
}
Returns HTTP 200 when both dependency checks succeed and HTTP 503 when a check fails.

Testing
Run Django tests inside the application container:


bash
docker compose exec web python manage.py test
Run tests with additional verbosity:


bash
docker compose exec web python manage.py test --verbosity 2
Logging
The application uses Python's logging framework to record important application events.

Examples include:

Task creation and updates.
Task deletion.
Password change failures.
Background task enqueue failures.
Stripe webhook verification.
Payment processing errors.
Application health check failures.
Future Improvements
Potential improvements for the project include:

Expand automated unit and integration test coverage.
Add comprehensive API documentation using OpenAPI and Swagger.
Improve service-layer separation for complex business logic.
Add more robust background task retry and failure handling.
Introduce structured logging and monitoring.
Add continuous integration and deployment using GitHub Actions.
Improve production deployment configuration.
Add database performance monitoring.
Expand payment functionality beyond the current test checkout flow.
Improve application security and deployment hardening.
Project Goals
LearnHub demonstrates practical backend engineering concepts through the development of a Django application.

Key areas of focus:

REST API development.
Authentication and authorization.
Relational database design.
Background task processing.
Payment integration.
File validation and uploads.
Database transactions.
Query optimization.
Docker-based development.
Application health monitoring.
Backend architecture and code organization.

Built with Python, Django, and a focus on backend engineering.
