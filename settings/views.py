from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import SiteSetting




@staff_member_required
def settings_dashboard(request):
    
    return render(request, 'settings/settings_dashboard.html')

import os
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

@staff_member_required
def edit_hero(request):
    if request.method == 'POST':
        if request.FILES.get('hero_bg_image'):
            file = request.FILES.get('hero_bg_image')
            
            # ===== ذخیره در پوشه static/images/ با اسم hero-bg.jpg =====
            static_path = os.path.join(settings.BASE_DIR, 'static', 'images')
            os.makedirs(static_path, exist_ok=True)
            
            file_path = os.path.join(static_path, 'hero-bg.jpg')
            
            # ===== حذف فایل قبلی =====
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # ===== ذخیره فایل جدید =====
            with open(file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            
            messages.success(request, '✅ تصویر هیرو با موفقیت تغییر کرد')
        else:
            messages.warning(request, 'هیچ تصویری انتخاب نشده است')
        return redirect('settings:edit_hero')
    
    hero_bg = SiteSetting.objects.filter(key='hero_bg_image').first()
    
    context = {
        'hero_bg': hero_bg.image.url if hero_bg and hero_bg.image else None,
    }
    return render(request, 'settings/edit_hero.html', context)


@staff_member_required
def edit_about(request):
    
    
    if request.method == 'POST':
        
        
        for key, value in request.POST.items():
            if key.startswith('about_'):
                
                setting, _ = SiteSetting.objects.get_or_create(key=key)
                setting.value = value
                setting.setting_type = 'about'
                setting.save()
                
        
        for key, file in request.FILES.items():
            if key.startswith('about_'):
                
                setting, _ = SiteSetting.objects.get_or_create(key=key)
                setting.image = file
                setting.setting_type = 'about'
                setting.save()
                
        
        messages.success(request, 'تنظیمات درباره ما ذخیره شد')
        
        return redirect('settings:edit_about')
    
    
    settings_dict = {}
    for setting in SiteSetting.objects.filter(setting_type='about'):
        if setting.image:
            settings_dict[setting.key] = setting.image.url
            
        else:
            settings_dict[setting.key] = setting.value or ''
            
    return render(request, 'settings/edit_about.html', {'settings': settings_dict})