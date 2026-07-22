# sliders/forms.py
from django import forms
from .models import Slider


class SliderForm(forms.ModelForm):
    class Meta:
        model = Slider
        fields = ['title', 'subtitle', 'image', 'link', 'link_text', 'position', 'order', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-4 py-2'}),
            'subtitle': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-4 py-2'}),
            'image': forms.FileInput(attrs={'class': 'w-full border rounded-lg px-4 py-2'}),
            'link': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-4 py-2'}),
            'link_text': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-4 py-2'}),
            'position': forms.Select(attrs={'class': 'w-full border rounded-lg px-4 py-2'}),
            'order': forms.NumberInput(attrs={'class': 'w-full border rounded-lg px-4 py-2'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-4 h-4'}),
        }