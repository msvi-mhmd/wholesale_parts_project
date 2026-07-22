# products/utils.py
import re
from difflib import SequenceMatcher

# کلمات اضافی برای حذف
STOP_WORDS = {
    'و', 'یا', 'به', 'از', 'برای', 'با', 'در', 'یک', 'این', 'آن',
    'های', 'تر', 'ترین', 'مشخصات', 'قیمت', 'فروش', 'نوع', 'مدل',
    'قطعه', 'لوازم', 'یدکی', 'اصل', 'درجه', 'یک', 'کیفیت'
}

def normalize_text(text):
    """نرمال‌سازی متن"""
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r'[^\w\s]', '', text)  # حذف علائم نگارشی
    text = re.sub(r'\s+', ' ', text)      # حذف فاصله‌های اضافی
    return text.strip()

def extract_words(text):
    """استخراج کلمات از متن (با حذف کلمات اضافی)"""
    text = normalize_text(text)
    words = text.split()
    # حذف کلمات اضافی
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]

def calculate_similarity_score(query, product_name, product_aliases):
    """
    محاسبه امتیاز شباهت بین عبارت جستجو و محصول
    بازگشت: عدد بین 0 تا 100
    """
    query_words = extract_words(query)
    if not query_words:
        return 0
    
    # لیست تمام نام‌های محصول (نام اصلی + نام‌های جایگزین)
    all_names = [product_name]
    if product_aliases:
        all_names.extend(product_aliases)
    
    best_score = 0
    
    for name in all_names:
        name_words = extract_words(name)
        if not name_words:
            continue
        
        # 1. امتیاز کلمات مشترک (70% وزن)
        common_words = set(query_words) & set(name_words)
        word_match_score = (len(common_words) / max(len(query_words), len(name_words))) * 70
        
        # 2. امتیاز ترتیب کلمات (20% وزن) - چک می‌کند کلمات به ترتیب آمده‌اند
        order_score = 0
        if len(common_words) >= 2:
            # بررسی ترتیب کلمات مشترک در نام محصول
            name_lower = normalize_text(name)
            query_phrase = ' '.join(query_words)
            if query_phrase in name_lower:
                order_score = 20
            else:
                # بررسی ترتیب نسبی
                name_indices = [name_lower.find(word) for word in common_words if word in name_lower]
                if len(name_indices) >= 2 and all(name_indices[i] < name_indices[i+1] for i in range(len(name_indices)-1)):
                    order_score = 15
        
        # 3. امتیاز شباهت رشته‌ای (10% وزن)
        string_similarity = SequenceMatcher(None, normalize_text(query), normalize_text(name)).ratio() * 10
        
        total_score = word_match_score + order_score + string_similarity
        best_score = max(best_score, total_score)
    
    return min(best_score, 100)  # حداکثر 100

def rank_products_by_relevance(products, query):
    """
    مرتب‌سازی محصولات بر اساس میزان ارتباط با جستجو
    """
    if not query:
        return products
    
    scored_products = []
    
    for product in products:
        # دریافت نام‌های جایگزین
        aliases = list(product.aliases.values_list('name', flat=True)) if hasattr(product, 'aliases') else []
        
        # محاسبه امتیاز
        score = calculate_similarity_score(query, product.name, aliases)
        
        # امتیاز ویژه برای محصولات پرفروش (مکانیسم tie-breaking)
        popularity_bonus = min(product.sold_number / 100, 10) if product.sold_number else 0
        
        final_score = score + popularity_bonus
        
        scored_products.append((product, final_score))
    
    # مرتب‌سازی بر اساس امتیاز (بیشترین اولویت)
    scored_products.sort(key=lambda x: x[1], reverse=True)
    
    return [p for p, score in scored_products]