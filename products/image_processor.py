# products/image_processor.py
import os
import uuid
from PIL import Image, ImageOps
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from io import BytesIO
import re


def process_product_images(product, images):
    """
    پردازش و بهینه‌سازی تصاویر محصول
    
    Args:
        product: مدل محصول
        images: لیست فایل‌های تصویر
    
    Returns:
        list: لیست مسیرهای تصاویر ذخیره شده
    """
    processed_images = []
    
    # ایجاد نام پایه از نام محصول
    base_name = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF]', '-', product.name)
    base_name = re.sub(r'-+', '-', base_name).strip('-')
    
    for i, image_file in enumerate(images):
        try:
            # باز کردن تصویر
            img = Image.open(image_file)
            
            # تبدیل به RGB (برای پشتیبانی از JPEG/PNG)
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # ===== 1. ایجاد تصویر اصلی 600x600 با کادر سفید =====
            main_image = resize_with_white_border(img, 600, 600)
            main_filename = f"products/{base_name}_{i+1}_{uuid.uuid4().hex[:8]}.webp"
            main_path = save_image_as_webp(main_image, main_filename)
            
            # ===== 2. ایجاد تصویر کوچک 180x180 برای کارت محصول =====
            thumb_image = resize_with_white_border(img, 180, 180)
            thumb_filename = f"products/thumbs/{base_name}_{i+1}_{uuid.uuid4().hex[:8]}.webp"
            thumb_path = save_image_as_webp(thumb_image, thumb_filename)
            
            processed_images.append({
                'main': main_path,
                'thumb': thumb_path,
                'is_main': (i == 0)
            })
            
        except Exception as e:
            print(f"Error processing image {i}: {e}")
            continue
    
    return processed_images


def resize_with_white_border(img, target_width, target_height):
    """
    تغییر اندازه تصویر با حفظ نسبت و اضافه کردن کادر سفید
    
    Args:
        img: شیء PIL Image
        target_width: عرض هدف
        target_height: ارتفاع هدف
    
    Returns:
        PIL Image: تصویر تغییر اندازه داده شده
    """
    # محاسبه نسبت تصویر اصلی
    original_width, original_height = img.size
    original_ratio = original_width / original_height
    target_ratio = target_width / target_height
    
    # تعیین اندازه جدید با حفظ نسبت
    if original_ratio > target_ratio:
        # تصویر پهن‌تر است
        new_width = target_width
        new_height = int(target_width / original_ratio)
    else:
        # تصویر بلندتر است
        new_height = target_height
        new_width = int(target_height * original_ratio)
    
    # تغییر اندازه تصویر
    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # ایجاد بوم جدید با پس‌زمینه سفید
    canvas = Image.new('RGB', (target_width, target_height), (255, 255, 255))
    
    # محاسبه موقعیت قرارگیری تصویر در مرکز
    x_offset = (target_width - new_width) // 2
    y_offset = (target_height - new_height) // 2
    
    # قرار دادن تصویر روی بوم
    canvas.paste(img_resized, (x_offset, y_offset))
    
    return canvas


def save_image_as_webp(image, filename):
    """
    ذخیره تصویر به صورت WebP با کیفیت بالا
    
    Args:
        image: شیء PIL Image
        filename: نام فایل مقصد
    
    Returns:
        str: مسیر فایل ذخیره شده
    """
    # ایجاد پوشه در صورت عدم وجود
    directory = os.path.dirname(filename)
    if directory:
        os.makedirs(f"media/{directory}", exist_ok=True)
    
    # ذخیره به صورت WebP
    buffer = BytesIO()
    image.save(buffer, format='WEBP', quality=85, optimize=True)
    buffer.seek(0)
    
    # ذخیره با استفاده از default_storage
    path = default_storage.save(filename, ContentFile(buffer.read()))
    
    return path


def get_thumb_url(product, default=False):
    """
    دریافت URL تصویر کوچک محصول
    
    Args:
        product: مدل محصول
        default: در صورت عدم وجود تصویر، تصویر پیش‌فرض برگردان
    
    Returns:
        str: URL تصویر
    """
    first_image = product.images.first()
    if first_image and first_image.thumb:
        return first_image.thumb.url
    elif first_image and first_image.image:
        return first_image.image.url
    else:
        return '/static/images/no-image.png'
    







