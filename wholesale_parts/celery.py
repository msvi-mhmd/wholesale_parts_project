# wholesale_parts/celery.py
import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wholesale_parts.settings')

app = Celery('wholesale_parts')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


# ===== وظیفه زمان‌بندی شده =====
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # هر 2 ساعت یکبار اجرا شود
    sender.add_periodic_task(
        crontab(minute='0', hour='*/2'),  # هر 2 ساعت
        sync_all_with_accounting.s(),
        name='sync_all_with_accounting_every_2_hours'
    )
    
    # همچنین می‌توانید برای تست، هر 5 دقیقه یکبار
    # sender.add_periodic_task(
    #     crontab(minute='*/5'),
    #     sync_all_with_accounting.s(),
    #     name='sync_all_with_accounting_every_5_minutes'
    # )


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')