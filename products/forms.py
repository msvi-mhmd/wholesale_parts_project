# products/forms.py
from django import forms
from .models import ProductComment

class ProductCommentForm(forms.ModelForm):
    class Meta:
        model = ProductComment
        fields = ['title', 'comment', 'rating']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500', 'placeholder': 'عنوان نظر (اختیاری)'}),
            'comment': forms.Textarea(attrs={'rows': 4, 'class': 'w-full border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500', 'placeholder': 'متن نظر خود را وارد کنید...'}),
            'rating': forms.Select(attrs={'class': 'w-full border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500'}),
        }