# sliders/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
import json

from .models import Slider
from .forms import SliderForm


@login_required
@staff_member_required
def slider_list(request):
    """لیست اسلایدرها"""
    sliders = Slider.objects.all().order_by('position', 'order')
    
    context = {
        'sliders': sliders,
    }
    return render(request, 'sliders/slider_list.html', context)

# sliders/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Slider
from .forms import SliderForm


@login_required
@staff_member_required
def slider_create(request):
    """ایجاد اسلایدر جدید"""
    if request.method == 'POST':
        form = SliderForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ اسلایدر با موفقیت ایجاد شد')
            return redirect('sliders:slider_list')
        else:
            # نمایش خطاهای فرم به صورت پیام
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'❌ {field}: {error}')
    else:
        form = SliderForm()
    
    context = {
        'form': form,
        'title': 'ایجاد اسلایدر جدید',
    }
    return render(request, 'sliders/slider_form.html', context)

@login_required
@staff_member_required
def slider_edit(request, slider_id):
    """ویرایش اسلایدر"""
    slider = get_object_or_404(Slider, id=slider_id)
    
    if request.method == 'POST':
        form = SliderForm(request.POST, request.FILES, instance=slider)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ اسلایدر با موفقیت ویرایش شد')
            return redirect('sliders:slider_list')
        else:
            # نمایش خطاهای فرم
            for field, errors in form.errors.items():
                field_label = form.fields[field].label if field in form.fields else field
                for error in errors:
                    messages.error(request, f'❌ {field_label}: {error}')
    else:
        form = SliderForm(instance=slider)
    
    context = {
        'form': form,
        'slider': slider,
        'title': 'ویرایش اسلایدر',
    }
    return render(request, 'sliders/slider_form.html', context)


@login_required
@staff_member_required
def slider_delete(request, slider_id):
    """حذف اسلایدر"""
    slider = get_object_or_404(Slider, id=slider_id)
    
    if request.method == 'POST':
        # حذف تصویر
        if slider.image:
            slider.image.delete()
        slider.delete()
        messages.success(request, '✅ اسلایدر با موفقیت حذف شد')
        return redirect('sliders:slider_list')
    
    context = {
        'slider': slider,
    }
    return render(request, 'sliders/slider_delete_confirm.html', context)


@login_required
@staff_member_required
def slider_toggle_status(request, slider_id):
    """تغییر وضعیت فعال/غیرفعال اسلایدر"""
    slider = get_object_or_404(Slider, id=slider_id)
    slider.is_active = not slider.is_active
    slider.save()
    
    status = 'فعال' if slider.is_active else 'غیرفعال'
    messages.success(request, f'✅ وضعیت اسلایدر به "{status}" تغییر کرد')
    return redirect('sliders:slider_list')


@login_required
@staff_member_required
def slider_reorder(request):
    """تغییر ترتیب اسلایدرها (API)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        slider_ids = data.get('ids', [])
        
        for index, slider_id in enumerate(slider_ids):
            Slider.objects.filter(id=slider_id).update(order=index)
        
        return JsonResponse({'success': True, 'message': 'ترتیب با موفقیت ذخیره شد'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    