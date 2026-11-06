from rest_framework import generics, permissions
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from django.db.models import Q
from django.utils import timezone

from .models import NewsArticle
from .serializers import NewsArticleSerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'ADMIN'
        )


class NewsArticleListCreateView(generics.ListCreateAPIView):
    serializer_class = NewsArticleSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        queryset = NewsArticle.objects.select_related('author')
        if not self.request.user.is_authenticated or self.request.user.role != 'ADMIN':
            return queryset.filter(
                Q(is_published=True)
                | Q(scheduled_for__lte=timezone.now(), is_published=False)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class NewsArticleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = NewsArticleSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        queryset = NewsArticle.objects.select_related('author')
        if not self.request.user.is_authenticated or self.request.user.role != 'ADMIN':
            return queryset.filter(
                Q(is_published=True)
                | Q(scheduled_for__lte=timezone.now(), is_published=False)
            )
        return queryset
