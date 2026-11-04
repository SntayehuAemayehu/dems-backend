from rest_framework import serializers

from .models import NewsArticle


class NewsArticleSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True, default='')

    class Meta:
        model = NewsArticle
        fields = [
            'id',
            'title',
            'summary',
            'content',
            'category',
            'image',
            'video',
            'is_published',
            'is_featured',
            'scheduled_for',
            'author',
            'author_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['author', 'created_at', 'updated_at']
