from django.db import models

class SiteSetting(models.Model):
    SETTING_TYPES = (
        ('about', 'درباره ما'),
        ('hero', 'هیرو'),
    )
    
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='settings/', blank=True, null=True)
    setting_type = models.CharField(max_length=50, choices=SETTING_TYPES, default='about')
    is_active = models.BooleanField(default=True)  # <--- این خط رو اضافه کن
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key