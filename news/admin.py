from django.contrib import admin

from .models import NewsArticle


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'is_published', 'is_featured', 'created_at')
    list_filter = ('is_published', 'is_featured', 'category')
    search_fields = ('title', 'summary', 'content')
