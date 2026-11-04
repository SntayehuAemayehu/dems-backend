from django.urls import path

from .views import NewsArticleDetailView, NewsArticleListCreateView

urlpatterns = [
    path('', NewsArticleListCreateView.as_view(), name='news-list'),
    path('<int:pk>/', NewsArticleDetailView.as_view(), name='news-detail'),
]
