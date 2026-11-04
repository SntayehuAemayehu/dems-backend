from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import NewsArticle


class NewsArticleApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            email='news-admin@example.com',
            password='test-password',
            full_name='News Admin',
            role='ADMIN',
        )
        self.teacher = user_model.objects.create_user(
            email='news-teacher@example.com',
            password='test-password',
            full_name='News Teacher',
            role='TEACHER',
        )
        self.published_article = NewsArticle.objects.create(
            title='Published update',
            summary='A public update',
            content='The full published story',
            is_published=True,
            author=self.admin,
        )
        self.draft_article = NewsArticle.objects.create(
            title='Unpublished draft',
            summary='A draft update',
            content='The private draft story',
            author=self.admin,
        )

    def test_public_news_only_includes_published_articles(self):
        response = self.client.get(reverse('news-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [article['title'] for article in response.data['results']]
        self.assertEqual(titles, ['Published update'])

    def test_public_cannot_open_an_unpublished_article(self):
        response = self.client.get(reverse('news-detail', args=[self.draft_article.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_scheduled_article_becomes_public_when_schedule_time_arrives(self):
        article = NewsArticle.objects.create(
            title='Scheduled update',
            summary='A scheduled update',
            content='The scheduled story',
            scheduled_for=timezone.now() - timedelta(minutes=1),
            author=self.admin,
        )

        response = self.client.get(reverse('news-detail', args=[article.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Scheduled update')

    def test_future_scheduled_article_is_not_public(self):
        article = NewsArticle.objects.create(
            title='Future update',
            summary='A future update',
            content='The future story',
            scheduled_for=timezone.now() + timedelta(days=1),
            author=self.admin,
        )

        response = self.client.get(reverse('news-detail', args=[article.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_create_news(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(reverse('news-list'), {
            'title': 'New announcement',
            'summary': 'A concise summary',
            'content': 'The complete story',
            'category': 'Announcement',
            'is_published': True,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['author'], self.admin.id)
        self.assertTrue(NewsArticle.objects.get(id=response.data['id']).is_published)

    def test_admin_can_create_multipart_scheduled_news(self):
        self.client.force_authenticate(user=self.admin)
        scheduled_for = timezone.now() + timedelta(days=1)
        response = self.client.post(reverse('news-list'), {
            'title': 'Tomorrow announcement',
            'summary': 'A scheduled summary',
            'content': 'This story goes live tomorrow',
            'category': 'Announcement',
            'is_published': 'false',
            'scheduled_for': scheduled_for.isoformat(),
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['is_published'])
        self.assertIsNotNone(response.data['scheduled_for'])

    def test_non_admin_cannot_manage_news(self):
        self.client.force_authenticate(user=self.teacher)
        response = self.client.post(reverse('news-list'), {
            'title': 'Unauthorized story',
            'summary': 'A concise summary',
            'content': 'The complete story',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
