import os
from pathlib import Path
from decouple import config  # <--- اضافه کن

# ===== بارگذاری .env =====
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ===== Django =====
SECRET_KEY = config('SECRET_KEY', default='django-insecure-your-secret-key-here')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    'accounts',
    'customers',
    'employees',
    'products',
    'invoices',
    'payments',
    'search',
    'reports',
    'accounting',
    'blog',
    'sms',
    'support',
    'sliders',
    'settings',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'wholesale_parts.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'products.context_processors.categories_processor',
            ],
        },
    },
]

# ===== Database =====
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='persian_gulf'),
        'USER': config('DB_USER', default='persian_gulf_user'),
        'PASSWORD': config('DB_PASSWORD', default='Moh@mad4217'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ===== Nikan API =====
ACCOUNTING_API = {
    'ENABLED': config('NIKAN_ENABLED', default=True, cast=bool),
    'BASE_URL': config('NIKAN_BASE_URL', default='https://derak.nikansoft.com/api'),
    'API_KEY': config('NIKAN_API_KEY', default=''),
    'USERNAME': config('NIKAN_USERNAME', default='golf'),
    'PASSWORD': config('NIKAN_PASSWORD', default='123456'),
    'TIMEOUT': config('NIKAN_TIMEOUT', default=300, cast=int),
}

LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# ===== Celery =====
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Tehran'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_STORE_EAGER_RESULT = True

# ===== Static & Media =====
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ===== Auth =====
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===== Zarinpal =====
ZARINPAL = {
    'ENABLED': config('ZARINPAL_ENABLED', default=False, cast=bool),
    'SANDBOX': config('ZARINPAL_SANDBOX', default=True, cast=bool),
    'MERCHANT_ID': config('ZARINPAL_MERCHANT_ID', default=''),
    'CALLBACK_URL': config('ZARINPAL_CALLBACK_URL', default=''),
}

# ===== SMS =====
SMS_CONFIG = {
    'ENABLED': config('SMS_ENABLED', default=False, cast=bool),
    'DRIVER': config('SMS_DRIVER', default='console'),
    'API_KEY': config('SMS_API_KEY', default=''),
    'SENDER': config('SMS_SENDER', default='1000'),
    'TEMPLATE': config('SMS_TEMPLATE', default='verification-code'),
}