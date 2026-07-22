# products/context_processors.py
from .models import MainCategory

def categories_processor(request):
    categories = MainCategory.objects.prefetch_related('subcategories').all()
    return {
        'all_categories': categories
    }