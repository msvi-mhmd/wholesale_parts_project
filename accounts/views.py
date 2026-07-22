# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from .models import RegistrationRequest, User
import random

from .models import User
from sms.utils import generate_otp_code

otp_storage = {}

def send_otp(request):
    """ارسال کد OTP"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    phone = request.POST.get('phone')
    
    if not phone or len(phone) != 11:
        return JsonResponse({'error': 'شماره تلفن معتبر وارد کنید'}, status=400)
    
    user = User.objects.filter(phone=phone).first()
    if not user:
        return JsonResponse({'error': 'کاربری با این شماره تلفن یافت نشد'}, status=404)
    
    code = generate_otp_code()
    otp_storage[phone] = {
        'code': code,
        'created_at': timezone.now(),
        'user_id': user.id
    }
    
    request.session['otp_phone'] = phone
    
    # ===== بررسی فعال بودن پیامک =====
    if not settings.SMS_CONFIG.get('ENABLED', False):
        print(f"📱 [SMS DISABLED] Code for {phone}: {code}")
        return JsonResponse({
            'success': True, 
            'message': 'کد تایید (فقط برای تست)'
        })
    
    # ===== ارسال پیامک واقعی =====
    sms = SMSManager()
    result = sms.send_verification_code(phone, code)
    
    if result.get('success'):
        return JsonResponse({
            'success': True, 
            'message': 'کد تایید ارسال شد'
        })
    else:
        return JsonResponse({
            'success': False,
            'error': result.get('message', 'خطا در ارسال پیامک')
        }, status=500)
    
    

def verify_otp(request):
    """تایید کد OTP"""
    phone = request.session.get('otp_phone')
    
    if not phone:
        return JsonResponse({'error': 'اطلاعات نامعتبر'}, status=400)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    otp_code = request.POST.get('otp')
    
    if not otp_code:
        return JsonResponse({'error': 'کد تایید را وارد کنید'}, status=400)
    
    stored_data = otp_storage.get(phone)
    
    if not stored_data:
        return JsonResponse({'error': 'کد تایید منقضی شده است'}, status=400)
    
    time_diff = timezone.now() - stored_data['created_at']
    if time_diff > timedelta(minutes=5):
        del otp_storage[phone]
        return JsonResponse({'error': 'کد تایید منقضی شده است'}, status=400)
    
    if stored_data['code'] == otp_code:
        user = User.objects.get(id=stored_data['user_id'])
        login(request, user)
        
        del otp_storage[phone]
        if 'otp_phone' in request.session:
            del request.session['otp_phone']
        
        return JsonResponse({'success': True, 'message': 'ورود موفق'})
    else:
        return JsonResponse({'error': 'کد تایید اشتباه است'}, status=400)


def resend_otp(request):
    """ارسال مجدد کد OTP"""
    phone = request.session.get('otp_phone')
    
    if not phone:
        messages.error(request, 'اطلاعات نامعتبر')
        return redirect('accounts:login')
    
    user = User.objects.filter(phone=phone).first()
    if not user:
        messages.error(request, 'کاربری با این شماره تلفن یافت نشد')
        return redirect('accounts:login')
    
    code = generate_otp_code()
    otp_storage[phone] = {
        'code': code,
        'created_at': timezone.now(),
        'user_id': user.id
    }
    

    
    messages.success(request, 'کد جدید با موفقیت ارسال شد')
    return redirect('accounts:verify_otp')

# accounts/views.py - ادامه فایل

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('accounts:dashboard_redirect')
        else:
            messages.error(request, 'نام کاربری یا رمز عبور اشتباه است')
    
    return render(request, 'accounts/login.html')


def register_request(request):
    if request.method == 'POST':
        national_id = request.POST.get('national_id')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        city = request.POST.get('city')
        street = request.POST.get('street')
        address = request.POST.get('address')
        invitation_code = request.POST.get('invitation_code')
        
        if not national_id or not first_name or not last_name or not phone:
            messages.error(request, 'لطفاً تمام فیلدهای ضروری را پر کنید')
            return redirect('accounts:register_request')
        
        if RegistrationRequest.objects.filter(national_id=national_id).exists():
            messages.error(request, 'این کد ملی قبلاً ثبت شده است')
            return redirect('accounts:register_request')
        
        if RegistrationRequest.objects.filter(phone=phone).exists():
            messages.error(request, 'این شماره تلفن قبلاً ثبت شده است')
            return redirect('accounts:register_request')
        
        try:
            request_obj = RegistrationRequest.objects.create(
                national_id=national_id,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email or '',
                city=city or '',
                street=street or '',
                address=address or '',
                invitation_code=invitation_code or '',
                status='pending',
                is_viewed=False
            )
            
            messages.success(
                request, 
                '✅ درخواست شما با موفقیت ثبت شد. همکاران ما به زودی با شما تماس خواهند گرفت.'
            )
            return redirect('accounts:login')
            
        except Exception as e:
            messages.error(request, f'خطا در ثبت درخواست: {str(e)}')
            return redirect('accounts:register_request')
    
    return render(request, 'accounts/register_request.html')


@login_required
def dashboard_redirect(request):
    if request.user.user_type == 'admin':
        return redirect('employees:admin_panel')
    elif request.user.user_type == 'employee':
        return redirect('employees:employee_panel')
    elif request.user.user_type == 'customer':
        return redirect('customers:customer_panel')
    else:
        return redirect('home')