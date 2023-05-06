from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

from ..models import Group, Post, Follow
from ..forms import PostForm
from ..views import POSTS_SHOWN

User = get_user_model()


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.posts_create = 13
        for post in range(cls.posts_create):
            Post.objects.create(
                author=cls.user,
                group=cls.group,
                text=f'Тестовый пост {post}',
            )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    def test_first_page_contains_ten_records(self):
        """Проверка отображения постов на первой странице"""
        reverse_name_paginator = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': self.group.slug}),
            reverse('posts:profile', kwargs={'username': 'auth'}),
        ]
        for reverse_name in reverse_name_paginator:
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.context['page_obj']),
                                 POSTS_SHOWN)

    def test_second_page_contains_three_records(self):
        """Проверка отображения постов на второй странице"""
        reverse_name_paginator = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': self.group.slug}),
            reverse('posts:profile', kwargs={'username': 'auth'}),
        ]
        for reverse_name in reverse_name_paginator:
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(
                    reverse_name + '?page=2')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.context['page_obj']),
                                 Post.objects.count() - POSTS_SHOWN)


class TestPagesTests(TestCase):
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
            group=cls.group,
            text='Тестовый пост',
        )
        cls.user_following = User.objects.create_user(username='following_me')
        cls.user_not_follow = User.objects.create_user(username='not_follow_u')

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.user_not_follow_u = Client()
        self.user_following_me = Client()
        self.user_not_follow_u.force_login(self.user_not_follow)
        self.user_following_me.force_login(self.user_following)
        self.post_shows = Post.objects.create(
            author=self.user,
            group=self.group,
            text='Второй пост'
        )
        self.group2 = Group.objects.create(
            title='группа',
            slug='slug',
            description='описание',
        )
        cache.clear()

    def test_pages_uses_correct_templates(self):
        """URL-адрес использует соответствующий шаблон"""
        template_page_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_list',
                    kwargs={'slug': 'test-slug'}): 'posts/group_list.html',
            reverse('posts:profile',
                    kwargs={'username': 'auth'}): 'posts/profile.html',
            reverse('posts:post_detail',
                    kwargs={'post_id': 1}): 'posts/post_detail.html',
            reverse('posts:post_edit',
                    kwargs={'pk': 1}): 'posts/post_create.html',
            reverse('posts:post_create'): 'posts/post_create.html',
        }
        for reverse_name, template in template_page_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_index_correct_context(self):
        """Шаблон index с правильным контескстом"""
        response = self.authorized_client.get(reverse('posts:index'))
        expected = list(Post.objects.all().order_by('-pub_date')[:POSTS_SHOWN])
        self.assertEqual(list(response.context['page_obj']), expected)

    def test_group_list_correct_context(self):
        """Шаблон group_list с правильным контекстом"""
        response = self.authorized_client.get(
            reverse('posts:group_list', args=[self.post.group.slug]))
        self.check_two_posts(obj=response.context['page_obj'][1])

    def test_post_detail_correct_context(self):
        """Шаблон post_detail с правильным контекстом"""
        response = self.authorized_client.get(
            reverse('posts:post_detail', args=[self.post.id])
        )
        self.check_two_posts(obj=response.context['post'])

    def test_profile_correct_context(self):
        """Шаблон profile с правильным контекстом"""
        response = self.client.get(
            reverse('posts:profile', args=[self.user.username])
        )
        self.check_two_posts(obj=response.context['page_obj'][1])

    def test_post_create_correct_context(self):
        """Шаблон post_create с правильным контекстом"""
        response = self.authorized_client.get(
            reverse('posts:post_create')
        )
        self.check_two_forms(response)

    def test_post_edit_correct_context(self):
        """Шаблон post_edit с правильным контекстом"""
        response = (self.authorized_client.get(
            reverse('posts:post_edit', args=[self.post.id])))
        self.check_two_forms(response)

    def test_post_not_on_dif_group(self):
        """Проверяем: новый пост не появляется в другой группе"""
        response = self.authorized_client.get(
            reverse('posts:group_list', args=[self.group2.slug])
        )
        self.assertNotIn(self.post_shows, response.context['page_obj'])

    def test_post_on_3_pages(self):
        """Новый пост отображается на трех страницах"""
        responses = [
            reverse('posts:index'),
            reverse('posts:group_list',
                    args=[self.post_shows.group.slug]),
            reverse('posts:profile', args=[self.user.username])
        ]
        for page in responses:
            self.assertIn(
                self.post_shows,
                self.authorized_client.get(page).context['page_obj']
            )

    def check_cache_index(self):
        """Проверка кэширования главной страницы"""
        response = self.authorized_client.get(reverse('posts:index'))
        posts = response.content
        new_post = Post.objects.create(
            text='test_new_post',
            author=self.author,
            group=self.group
        )
        response_old = self.authorized_client.get(reverse('posts:index'))
        old_posts = response_old.content
        new_post.delete()
        self.assertEqual(old_posts, posts)
        cache.clear()
        response_new = self.authorized_client.get(reverse('posts:index'))
        new_posts = response_new.content
        self.assertNotEqual(old_posts, new_posts)

    def test_follow_ones(self):
        """Проверка, что можно подписываться и отписываться"""
        self.authorized_client.get(reverse(
            'posts:profile_follow', args=[self.user_following_me]
        ))
        self.assertTrue(
            Follow.bjects.filter(
                user=self.authorized_client,
                author=self.user_following_me,
            ).exists()
        )
        self.authorized_client.get(reverse(
            'posts:profile_unfollow', args=[self.user_following_me]
        ))
        self.assertFalse(
            Follow.bjects.filter(
                user=self.authorized_client,
                author=self.user_following_me,
            ).exists()
        )

    def test_new_post_for_followers(self):
        """Проверка, что новая запись автора видна тем,
        кто на него подписан и НЕТ для тех, кто не подписан"""
        Follow.objects.create(
            user=self.user,
            author=self.user_following
        )
        new_post = Post.objects.create(
            author=self.user_following,
            text='Приветствую всех подписочников',
        )
        response = self.authorized_client.get(reverse('posts:follow_index'))
        self.assertIn(new_post, response.context['page_obj'])
        response = self.user_not_follow_u.get(reverse('posts:follow_index'))
        self.assertNotIn(new_post, response.context['page_obj'])

    def test_context_with_image(self):
        image = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=image,
            content_type='image/gif'
        )
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.pk,
            'image': uploaded,
        }
        self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        reverse_names = [
            reverse('posts:index'),
            reverse('posts:group_list',
                    args=[self.group.pk]),
            reverse('posts:profile', args=[self.user.username]),
            reverse('posts:post_detail', args=[self.post.pk])
        ]
        for revers_name in reverse_names:
            response = self.authorized_client.get(revers_name)
            if 'page_obj' in response.context:
                first_obj = response.context['page_obj'][0]
                self.assertEqual(first_obj.image, uploaded.content)
            else:
                post = response.context['post']
                self.assertEqual(post.image, form_data['image'])

    def check_two_posts(self, obj):
        """Проверка двух постов"""
        self.assertEqual(obj.author, self.post.author)
        self.assertEqual(obj.text, self.post.text)
        self.assertEqual(obj.group, self.post.group)
        self.assertEqual(obj.pk, self.post.pk)

    def check_two_forms(self, response):
        """Проверка форм"""
        self.assertEqual(len(response.context['form'].fields), 3)
        self.assertIsInstance(response.context['form'], PostForm)
