# support/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
from .models import Ticket, TicketReply, TicketCategory


# support/views.py - اصلاح تابع ticket_list

# support/views.py - اضافه کردن این تابع

@login_required
def admin_ticket_list(request):
    """لیست همه تیکت‌ها برای مدیران و کارمندان"""
    
    # فقط ادمین و کارمند دسترسی دارند
    if request.user.user_type not in ['admin', 'employee']:
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('support:ticket_list')
    
    # دریافت همه تیکت‌ها به ترتیب تاریخ (جدیدترین اول)
    tickets = Ticket.objects.all().order_by('-created_at')
    
    # فیلتر بر اساس وضعیت
    status_filter = request.GET.get('status', '')
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    
    # فیلتر بر اساس اولویت
    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)
    
    # جستجو
    search = request.GET.get('search', '')
    if search:
        tickets = tickets.filter(
            Q(ticket_id__icontains=search) |
            Q(title__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__phone__icontains=search)
        )
    
    # صفحه‌بندی
    paginator = Paginator(tickets, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # آمار
    stats = {
        'total': Ticket.objects.count(),
        'open': Ticket.objects.filter(status='open').count(),
        'in_progress': Ticket.objects.filter(status='in_progress').count(),
        'answered': Ticket.objects.filter(status='answered').count(),
        'closed': Ticket.objects.filter(status='closed').count(),
    }
    
    context = {
        'tickets': page_obj,
        'stats': stats,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search': search,
        'ticket_status_choices': Ticket.STATUS_CHOICES,
    }
    return render(request, 'support/admin_ticket_list.html', context)


@login_required
def ticket_list(request):
    """لیست تیکت‌های کاربر - ساده و مینیمال"""
    
    # فقط تیکت‌های خود کاربر را نشان بده
    tickets = Ticket.objects.filter(user=request.user).order_by('-created_at')
    
    # فیلتر بر اساس وضعیت
    status_filter = request.GET.get('status', '')
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    
    # صفحه‌بندی
    paginator = Paginator(tickets, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tickets': page_obj,
        'status_filter': status_filter,
    }
    return render(request, 'support/ticket_list.html', context)

@login_required
def ticket_detail(request, ticket_id):
    """جزئیات تیکت"""
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # بررسی دسترسی
    if request.user.user_type == 'customer' and ticket.user != request.user:
        messages.error(request, 'شما دسترسی به این تیکت را ندارید')
        return redirect('support:ticket_list')
    
    context = {
        'ticket': ticket,
        'is_admin_or_employee': request.user.user_type in ['admin', 'employee'],
    }
    return render(request, 'support/ticket_detail.html', context)


@login_required
def create_ticket(request):
    """ایجاد تیکت جدید"""
    # فقط مشتریان می‌توانند تیکت ایجاد کنند
    if request.user.user_type not in ['customer', 'admin', 'employee']:
        messages.error(request, 'شما دسترسی ایجاد تیکت را ندارید')
        return redirect('support:ticket_list')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        category_id = request.POST.get('category')
        message = request.POST.get('message')
        priority = request.POST.get('priority', 'normal')
        attachment = request.FILES.get('attachment')
        
        if not title or not message:
            messages.error(request, 'لطفاً عنوان و پیام را وارد کنید')
            return redirect('support:create_ticket')
        
        category = None
        if category_id:
            category = get_object_or_404(TicketCategory, id=category_id, is_active=True)
        
        ticket = Ticket.objects.create(
            user=request.user,
            category=category,
            title=title,
            message=message,
            priority=priority,
            attachment=attachment,
            status='open'
        )
        
        messages.success(request, f'  تیکت شما با شماره {ticket.ticket_id} ثبت شد')
        return redirect('support:ticket_detail', ticket_id=ticket.ticket_id)
    
    categories = TicketCategory.objects.filter(is_active=True)
    context = {
        'categories': categories,
    }
    return render(request, 'support/create_ticket.html', context)


@login_required
def ticket_reply(request, ticket_id):
    """پاسخ به تیکت"""
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # بررسی دسترسی
    if request.user.user_type == 'customer' and ticket.user != request.user:
        messages.error(request, 'شما دسترسی به این تیکت را ندارید')
        return redirect('support:ticket_list')
    
    if request.method != 'POST':
        return redirect('support:ticket_detail', ticket_id=ticket.ticket_id)
    
    message = request.POST.get('message')
    attachment = request.FILES.get('attachment')
    is_internal = request.POST.get('is_internal') == 'on'
    
    # فقط ادمین و کارمند می‌توانند پاسخ داخلی بدهند
    if is_internal and request.user.user_type not in ['admin', 'employee']:
        messages.error(request, 'شما دسترسی پاسخ داخلی را ندارید')
        return redirect('support:ticket_detail', ticket_id=ticket.ticket_id)
    
    if not message:
        messages.error(request, 'لطفاً متن پیام را وارد کنید')
        return redirect('support:ticket_detail', ticket_id=ticket.ticket_id)
    
    reply = TicketReply.objects.create(
        ticket=ticket,
        user=request.user,
        message=message,
        attachment=attachment,
        is_internal=is_internal
    )
    
    # بروزرسانی وضعیت تیکت
    if request.user.user_type in ['admin', 'employee']:
        ticket.status = 'answered'
        ticket.answered_at = timezone.now()
        ticket.assigned_to = request.user
    else:
        ticket.status = 'open'
    
    ticket.save()
    
    messages.success(request, 'پاسخ شما با موفقیت ثبت شد')
    return redirect('support:ticket_detail', ticket_id=ticket.ticket_id)


@login_required
def ticket_status_update(request, ticket_id):
    """تغییر وضعیت تیکت (فقط برای ادمین و کارمند)"""
    if request.user.user_type not in ['admin', 'employee']:
        messages.error(request, 'شما دسترسی لازم را ندارید')
        return redirect('support:ticket_list')
    
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in dict(Ticket.STATUS_CHOICES):
            ticket.status = status
            if status == 'closed':
                ticket.closed_at = timezone.now()
            elif status == 'in_progress':
                ticket.assigned_to = request.user
            ticket.save()
            messages.success(request, f'وضعیت تیکت به "{ticket.get_status_display()}" تغییر کرد')
    
    return redirect('support:ticket_detail', ticket_id=ticket.ticket_id)


@login_required
def ticket_close(request, ticket_id):
    """بستن تیکت (کاربر یا ادمین)"""
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # بررسی دسترسی
    if request.user.user_type == 'customer' and ticket.user != request.user:
        messages.error(request, 'شما دسترسی به این تیکت را ندارید')
        return redirect('support:ticket_list')
    
    ticket.status = 'closed'
    ticket.closed_at = timezone.now()
    ticket.save()
    
    messages.success(request, 'تیکت با موفقیت بسته شد')

    if request.user.user_type not in ['admin', 'employee']:
        return redirect('support:ticket_list')
    
    else:
        return redirect('support:admin_ticket_list')


@login_required
def ticket_delete(request, ticket_id):
    """حذف تیکت (فقط ادمین)"""
    if request.user.user_type != 'admin':
        messages.error(request, 'شما دسترسی حذف تیکت را ندارید')
        return redirect('support:ticket_list')
    
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    if request.method == 'POST':
        ticket.delete()
        messages.success(request, 'تیکت با موفقیت حذف شد')
        return redirect('support:admin_ticket_list')
    
    context = {
        'ticket': ticket,
    }
    return render(request, 'support/ticket_delete_confirm.html', context)

# support/views.py - اضافه کردن این توابع در انتهای فایل

@login_required
def admin_ticket_list(request):
    """لیست همه تیکت‌ها برای مدیران و کارمندان"""
    
    # فقط ادمین و کارمند دسترسی دارند
    if request.user.user_type not in ['admin', 'employee']:
        messages.error(request, 'شما دسترسی به این صفحه را ندارید')
        return redirect('support:ticket_list')
    
    # دریافت همه تیکت‌ها به ترتیب تاریخ (جدیدترین اول)
    tickets = Ticket.objects.all().order_by('-created_at')
    
    # فیلتر بر اساس وضعیت
    status_filter = request.GET.get('status', '')
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    
    # فیلتر بر اساس اولویت
    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)
    
    # جستجو
    search = request.GET.get('search', '')
    if search:
        tickets = tickets.filter(
            Q(ticket_id__icontains=search) |
            Q(title__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__phone__icontains=search)
        )
    
    # صفحه‌بندی
    paginator = Paginator(tickets, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # آمار
    stats = {
        'total': Ticket.objects.count(),
        'open': Ticket.objects.filter(status='open').count(),
        'in_progress': Ticket.objects.filter(status='in_progress').count(),
        'answered': Ticket.objects.filter(status='answered').count(),
        'closed': Ticket.objects.filter(status='closed').count(),
    }
    
    context = {
        'tickets': page_obj,
        'stats': stats,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search': search,
        'ticket_status_choices': Ticket.STATUS_CHOICES,
    }
    return render(request, 'support/admin_ticket_list.html', context)


@login_required
def admin_ticket_status_update(request, ticket_id):
    """تغییر وضعیت تیکت توسط ادمین یا کارمند (API)"""
    
    # فقط ادمین و کارمند دسترسی دارند
    if request.user.user_type not in ['admin', 'employee']:
        return JsonResponse({'success': False, 'error': 'شما دسترسی لازم را ندارید'}, status=403)
    
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    import json
    try:
        data = json.loads(request.body)
        status = data.get('status')
        
        if status not in dict(Ticket.STATUS_CHOICES):
            return JsonResponse({'success': False, 'error': 'وضعیت نامعتبر است'}, status=400)
        
        ticket.status = status
        if status == 'closed':
            ticket.closed_at = timezone.now()
        elif status == 'in_progress':
            ticket.assigned_to = request.user
        ticket.save()
        
        return JsonResponse({
            'success': True,
            'message': f'وضعیت تیکت به "{ticket.get_status_display()}" تغییر کرد',
            'status': ticket.status,
            'status_display': ticket.get_status_display()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def admin_ticket_delete(request, ticket_id):
    """حذف تیکت توسط ادمین"""
    
    # فقط ادمین دسترسی دارد
    if request.user.user_type != 'admin':
        messages.error(request, 'شما دسترسی حذف تیکت را ندارید')
        return redirect('support:admin_ticket_list')
    
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    if request.method == 'POST':
        ticket.delete()
        messages.success(request, 'تیکت با موفقیت حذف شد')
        return redirect('support:admin_ticket_list')
    
    context = {
        'ticket': ticket,
    }
    return render(request, 'support/admin_ticket_delete_confirm.html', context)