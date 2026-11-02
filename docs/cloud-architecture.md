# Cloud Architecture

## EC2
Runs:
- Django
- Celery

## RDS
Runs:
- PostgreSQL

## S3
Stores:
- User uploads
- Images
- Documents

## IAM
Controls:
- AWS permissions
- Application access

## VPC
Provides:
- Network isolation
- Public/private networking

## Security Groups
Control:
- Allowed network traffic
- Ports


################################

                         INTERNET
                             │
                             ▼
                           AWS
                             │
                           VPC
                             │
                             ▼
                           EC2
                      ┌──────┴──────┐
                      │             │
                    Django        Celery
                      │
             ┌────────┼─────────┐
             │        │         │
             ▼        ▼         ▼
            RDS       S3      RabbitMQ
        PostgreSQL   Files     / Broker
