from django.conf import settings
from django.db import models


class NewsArticle(models.Model):
    title = models.CharField(max_length=200)
    summary = models.CharField(max_length=400)
    content = models.TextField()
    category = models.CharField(max_length=80, default='Announcement')
    image = models.ImageField(upload_to='news/images/%Y/%m/', blank=True, null=True)
    video = models.FileField(upload_to='news/videos/%Y/%m/', blank=True, null=True)
    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='news_articles',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
