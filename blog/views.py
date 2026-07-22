# blog/views.py
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import BlogPost, BlogCategory

def blog_list(request):
    posts = BlogPost.objects.filter(is_published=True)
    
    category_slug = request.GET.get('category')
    if category_slug:
        posts = posts.filter(category__slug=category_slug)
    
    paginator = Paginator(posts, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = BlogCategory.objects.filter(posts__is_published=True).distinct()
    
    context = {
        'posts': page_obj,
        'categories': categories,
    }
    return render(request, 'blog/list.html', context)

def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)
    post.view_count += 1
    post.save()
    
    # پست‌های مرتبط
    related_posts = BlogPost.objects.filter(
        category=post.category,
        is_published=True
    ).exclude(id=post.id)[:3]
    
    context = {
        'post': post,
        'related_posts': related_posts,
    }
    return render(request, 'blog/detail.html', context)