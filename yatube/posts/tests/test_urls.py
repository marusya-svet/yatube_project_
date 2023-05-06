from django.contrib.auth import get_user_model
from django.test import TestCase, Client

from ..models import Post, Group

User = get_user_model()


class StaticURLTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
        )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

        self.user2 = User.objects.create_user(username='noname')
        self.author = Client()
        self.author.force_login(self.user2)

    def test_urls_templates(self):
        """Проверка соответсвия шаблонов и url-адресов доступные всем"""
        url_template_name = {
            '/': 'posts/index.html',
            f'/group/{self.group.slug}/': 'posts/group_list.html',
            f'/profile/{self.user.username}/': 'posts/profile.html',
            f'/posts/{self.post.id}/': 'posts/post_detail.html',
        }

        for address, template in url_template_name.items():
            with self.subTest(address=address):
                response = self.client.get(address)
                self.assertTemplateUsed(response, template)

    def test_url_template_authorized(self):
        response = self.authorized_client.get('/create/')
        self.assertEqual(response.status_code, 200)

    def test_comment_authorized(self):
        """Проверка, что только авторизированный пользователь может
        оставлять комментарии"""
        response = self.authorized_client.get(
            f'/posts/{self.post.id}/comment/'
        )
        self.assertEqual(response.status_code, 302)

    def test_url_template_author(self):
        response = self.author.get(f'/posts/{self.post.id}/edit/')
        self.assertEqual(response.status_code, 302)

    def test_unexisting_page(self):
        """У страницы 404 кастомный шаблон"""
        response = self.client.get('/unexisting_page/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, 'core/404.html')

    def test_csrf_castom(self):
        """У страницы 403 кастомный шаблон"""
        def server_error():
            return HttpResponseForbidden()
        response = server_error()
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, 'core/403csrf.html')

    def test_redirect_anonymous(self):
        """Проверка, что анонимному пользователю не доступны
        страницы edit, create, comment, un/follow"""
        url_redirect = {
            f'/posts/{self.post.pk}/edit/':
                f'/auth/login/?next=/posts/{self.post.pk}/edit/',
            '/create/': '/auth/login/?next=/create/',
            f'/posts/{self.post.pk}/comment/':
                f'/auth/login/?next=/posts/{self.post.pk}/comment/',
            f'/profile/{self.user.username}/follow/':
                f'/auth/login/?next=/profile/{self.user.username}/follow/',
            f'/profile/{self.user.username}/unfollow/':
                f'/auth/login/?next=/profile/{self.user.username}/unfollow/'
        }
        for address, redirect in url_redirect.items():
            with self.subTest(address=address):
                response = self.client.get(address)
                self.assertRedirects(response, redirect)
