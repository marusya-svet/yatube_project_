import shutil
import tempfile

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.cache import cache

from ..models import Post, Group, Comment

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostCreateFormTests(TestCase):
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
            group=cls.group,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    def test_create_post(self):
        """При отправке валидной формы создается пост"""
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый текст поста',
            'group': self.group.pk,
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True,
        )
        new_post = Post.objects.latest('id')
        self.assertRedirects(response, reverse(
            'posts:profile', args=[self.user.username]))
        self.assertEqual(Post.objects.count(), posts_count + 1)
        self.assertEqual(new_post.text, form_data['text'])
        self.assertEqual(new_post.group.pk, form_data['group'])

    def test_edit_post(self):
        """При редактирование поста изменяется пост с post_id"""
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Измененный пост',
            'group': self.group.pk,
        }
        response = self.authorized_client.post(
            reverse('posts:post_edit', args={self.post.pk}),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(response, reverse(
            'posts:post_detail', args={self.post.pk}))
        self.post.refresh_from_db()
        self.assertEqual(self.post.text, form_data['text'])
        self.assertEqual(Post.objects.count(), posts_count)

    def test_image_post(self):
        """При отправке поста с картинкой создается запись в бд"""
        posts_count = Post.objects.count()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.pk,
            'image': uploaded,
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response, reverse(
            'posts:profile', args=[self.user.username]))
        self.assertEqual(Post.objects.count(), posts_count + 1)
        new_post = Post.objects.latest('id')
        self.assertTrue(
            Post.objects.filter(
                text=new_post.text,
                group=new_post.group,
                image='posts/small.gif'
            ).exists()
        )
        responses = [
            reverse('posts:index'),
            reverse('posts:group_list',
                    args=[new_post.group.slug]),
            reverse('posts:profile', args=[self.user.username]),
        ]
        for reverse_name in responses:
            response = self.authorized_client.get(reverse_name)
            self.assertIn(new_post, response.context['page_obj'])
        response = self.authorized_client.get(reverse(
            'posts:post_detail', args=[new_post.pk]))
        self.assertEqual(new_post, response.context['post'])

    def test_comment_shows_on_post(self):
        """При отпраке комментария он создается под постом"""
        comments_count = Comment.objects.count()
        form_data = {
            'text': 'Тестовый текст комментария'
        }
        response = self.authorized_client.post(
            reverse('posts:add_comment', args=[self.post.pk]),
            data=form_data,
            follow=True,
        )
        new_comment = Comment.objects.latest('id')
        self.assertRedirects(response, reverse(
            'posts:post_detail', args=[self.post.pk]))
        self.assertEqual(Comment.objects.count(), comments_count + 1)
        self.assertEqual(new_comment.text, form_data['text'])
