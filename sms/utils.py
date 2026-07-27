# sms/utils.py
import random
from django.conf import settings
import requests
import json

# تلاش برای import کاوه‌نگار
try:
    from kavenegar import KavenegarAPI, APIException, HTTPException
    KAVENEGAR_AVAILABLE = True
except ImportError:
    KAVENEGAR_AVAILABLE = False


def generate_otp_code():
    """تولید کد OTP ۶ رقمی"""
    return str(random.randint(100000, 999999))


class SMSManager:
    """مدیریت ارسال پیامک"""
    
    def __init__(self):
        self.driver = settings.SMS_CONFIG.get('DRIVER', 'console')
        self.api_key = settings.SMS_CONFIG.get('API_KEY', '')
        self.sender = settings.SMS_CONFIG.get('SENDER', '1000')
        self.template = settings.SMS_CONFIG.get('TEMPLATE', 'verification-code')
    
    def send_verification_code(self, phone, code):
        """ارسال کد تایید به شماره تلفن"""
        if self.driver == 'console':
            print(code)
            return
        elif self.driver == 'kavenegar':
            return self._send_kavenegar(phone, code)
        elif self.driver == 'ghasedak':
            return self._send_ghasedak(phone, code)
        elif self.driver == 'rahpal':
            return self._send_rahpal(phone, code)
        else:
            return self._send_console(phone, code)
    
    def _send_console(self, phone, code):
        """ارسال در کنسول (برای تست)"""
        print(f"📱 ارسال کد تایید به {phone}: {code}")
        return {'success': True, 'message': f'کد تایید: {code}'}
    
    def _send_kavenegar(self, phone, code):
        """ارسال از طریق کاوه‌نگار با استفاده از SDK رسمی"""
        if not KAVENEGAR_AVAILABLE:
            print("⚠️ کتابخانه kavenegar نصب نیست! pip install kavenegar")
            return self._send_console(phone, code)
        
        try:
            api = KavenegarAPI(self.api_key)
            params = {
                'receptor': phone,
                'template': self.template,
                'token': code,
                'type': 'sms'
            }
            response = api.verify_lookup(params)
            print(f"📱 کد تایید به {phone} ارسال شد: {code}")
            return {'success': True, 'message': 'کد تایید ارسال شد'}
        except APIException as e:
            print(f"  خطای API کاوه‌نگار: {e}")
            return {'success': False, 'message': str(e)}
        except HTTPException as e:
            print(f"  خطای HTTP کاوه‌نگار: {e}")
            return {'success': False, 'message': str(e)}
        except Exception as e:
            print(f"  خطای ناشناخته: {e}")
            return {'success': False, 'message': str(e)}
    
    def _send_kavenegar_requests(self, phone, code):
        """ارسال از طریق کاوه‌نگار با requests (بدون SDK)"""
        try:
            url = f'https://api.kavenegar.com/v1/{self.api_key}/verify/lookup.json'
            data = {
                'receptor': phone,
                'token': code,
                'template': self.template
            }
            response = requests.post(url, data=data)
            result = response.json()
            if result.get('return', {}).get('status') == 200:
                print(f"📱 کد تایید به {phone} ارسال شد: {code}")
                return {'success': True, 'message': 'کد تایید ارسال شد'}
            else:
                error_msg = result.get('return', {}).get('message', 'خطای ناشناخته')
                print(f"  خطا: {error_msg}")
                return {'success': False, 'message': error_msg}
        except Exception as e:
            print(f"  خطا: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def _send_ghasedak(self, phone, code):
        """ارسال از طریق غسداک"""
        try:
            url = 'https://api.ghasedak.io/v2/sms/send/simple'
            headers = {'apikey': self.api_key}
            data = {
                'message': f'کد تایید شما: {code}',
                'receptor': phone,
                'sender': self.sender
            }
            response = requests.post(url, headers=headers, data=data)
            result = response.json()
            if result.get('result', {}).get('code') == 200:
                print(f"📱 کد تایید به {phone} ارسال شد: {code}")
                return {'success': True, 'message': 'کد تایید ارسال شد'}
            else:
                return {'success': False, 'message': result.get('message', 'خطا در ارسال')}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def _send_rahpal(self, phone, code):
        """ارسال از طریق راه‌پال"""
        try:
            url = f'https://api.rahpal.com/api/v1/sms/send'
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            data = {
                'to': [phone],
                'message': f'کد تایید شما: {code}',
                'sender': self.sender
            }
            response = requests.post(url, headers=headers, json=data)
            result = response.json()
            if result.get('status') == 'success':
                print(f"📱 کد تایید به {phone} ارسال شد: {code}")
                return {'success': True, 'message': 'کد تایید ارسال شد'}
            else:
                return {'success': False, 'message': result.get('message', 'خطا در ارسال')}
        except Exception as e:
            return {'success': False, 'message': str(e)}