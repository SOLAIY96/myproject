import time

from celery import shared_task


# Week 11
@shared_task
def send_email_task():
    print("Sending email...")
    time.sleep(5)
    print("Email sent!")
    return "Email completed"


@shared_task
def generate_report():
    print("Generating report...")
    time.sleep(10)
    print("Report generated!")
    return "Report completed"


@shared_task
def export_tasks_to_csv():
    print("Exporting tasks...")
    time.sleep(5)
    print("Export completed!")
    return "CSV export completed"


@shared_task
def process_image():
    print("Processing image...")
    time.sleep(8)
    print("Image processing completed!")
    return "Image processed"


@shared_task
def send_task_notification(task_id):
    print(f"Notification for task {task_id}")


# Week 12
@shared_task
def successful_task():
    print("Task started")
    return "Task completed"


@shared_task
def failing_task():
    print("Task started")
    raise Exception("Something went wrong")


@shared_task(bind=True, max_retries=3)
def retrying_task(self):
    try:
        # simulate temporary failure
        ...
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)
