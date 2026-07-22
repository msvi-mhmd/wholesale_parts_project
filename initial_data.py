# initial_data.py - اجرا با python manage.py shell < initial_data.py
from django.contrib.auth import get_user_model
from employees.models import EmployeePermission, Employee
from customers.models import CustomerLevel
from invoices.models import InvoiceStatus
from payments.models import PaymentType

User = get_user_model()

# ایجاد سطوح مشتری
levels = [
    {'name': 'برنزی', 'min_credit': 0, 'discount_percent': 0, 'priority': 1},
    {'name': 'نقره‌ای', 'min_credit': 10000000, 'discount_percent': 5, 'priority': 2},
    {'name': 'طلایی', 'min_credit': 50000000, 'discount_percent': 10, 'priority': 3},
    {'name': 'پلاتینیوم', 'min_credit': 100000000, 'discount_percent': 15, 'priority': 4},
]

for level in levels:
    CustomerLevel.objects.get_or_create(
        name=level['name'],
        defaults=level
    )

# ایجاد وضعیت‌های فاکتور
statuses = [
    {'name': 'در انتظار تایید', 'code': 'PENDING', 'is_final': False},
    {'name': 'تایید شده', 'code': 'CONFIRMED', 'is_final': True},
    {'name': 'رد شده', 'code': 'REJECTED', 'is_final': True},
]

for status in statuses:
    InvoiceStatus.objects.get_or_create(
        code=status['code'],
        defaults=status
    )

# ایجاد انواع پرداخت
payment_types = [
    {'name': 'کارت به کارت', 'code': 'CARD'},
    {'name': 'واریز بانکی', 'code': 'BANK'},
    {'name': 'پرداخت از اعتبار', 'code': 'CREDIT'},
]

for pt in payment_types:
    PaymentType.objects.get_or_create(
        code=pt['code'],
        defaults=pt
    )

# ایجاد دسترسی‌های کارمندان
permissions = [
    ('view_customers', 'مشاهده مشتریان'),
    ('edit_customers', 'ویرایش مشتریان'),
    ('add_customers', 'افزودن مشتری'),
    ('view_products', 'مشاهده محصولات'),
    ('edit_products', 'ویرایش محصولات'),
    ('add_products', 'افزودن محصول'),
    ('view_invoices', 'مشاهده فاکتورها'),
    ('confirm_invoices', 'تایید فاکتورها'),
    ('view_payments', 'مشاهده پرداخت‌ها'),
    ('confirm_payments', 'تایید پرداخت‌ها'),
    ('view_reports', 'مشاهده گزارشات'),
]

for code, name in permissions:
    EmployeePermission.objects.get_or_create(
        code=code,
        defaults={'name': name}
    )

print("داده‌های اولیه با موفقیت ایجاد شدند!")