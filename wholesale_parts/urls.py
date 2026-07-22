# wholesale_parts/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.homepage, name='home'),
    path('about/', views.about_page, name='about'),
    path('accounts/', include('accounts.urls')),
    path('customers/', include('customers.urls')),
    path('employees/', include('employees.urls')),
    path('products/', include('products.urls')),
    path('invoices/', include('invoices.urls')),
    path('payments/', include('payments.urls')),
    path('search/', include('search.urls')),
    path('reports/', include('reports.urls')),
    path('accounting/', include('accounting.urls')),
    path('terms/', views.terms_and_conditions, name='terms'),
    path('registration-guide/', views.registration_guide, name='registration_guide'),
    path('history/', views.history, name='history'),
    path('blog/', include('blog.urls')),
    path('faq/', views.faq, name='faq'),
    path('support/', include('support.urls')),
    path('sliders/', include('sliders.urls')),
    path('settings/', include('settings.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)