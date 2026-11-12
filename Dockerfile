
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run Django with Gunicorn
CMD ["gunicorn", "learnhub.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
