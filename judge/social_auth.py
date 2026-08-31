import logging
import re
from operator import itemgetter
from urllib.parse import quote

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from requests import HTTPError
from reversion import revisions
from social_core.backends.github import GithubOAuth2
from social_core.exceptions import InvalidEmail, SocialAuthBaseException
from social_core.pipeline.partial import partial
from social_django.middleware import SocialAuthExceptionMiddleware as OldSocialAuthExceptionMiddleware

from judge.forms import ProfileForm
from judge.models import Language, Profile

logger = logging.getLogger('judge.social_auth')


class GitHubSecureEmailOAuth2(GithubOAuth2):
    name = 'github-secure'

    def user_data(self, access_token, *args, **kwargs):
        data = self._user_data(access_token)
        try:
            emails = self._user_data(access_token, '/emails')
        except (HTTPError, ValueError, TypeError):
            emails = []

        emails = [(e.get('email'), e.get('primary'), 0) for e in emails if isinstance(e, dict) and e.get('verified')]
        emails.sort(key=itemgetter(1), reverse=True)
        emails = list(map(itemgetter(0), emails))

        if emails:
            data['email'] = emails[0]
        else:
            data['email'] = None

        return data


def slugify_username(username, renotword=re.compile(r'[^\w]')):
    return renotword.sub('', username.replace('-', '_'))


class InvalidHNUEEmail(SocialAuthBaseException):
    def __init__(self, backend, email=None):
        self.email = email
        super().__init__(backend)

    def __str__(self):
        return 'Chỉ chấp nhận đăng nhập bằng Email sinh viên HNUE có định dạng stu<mã sinh viên 9 chữ số>@hnue.edu.vn (Ví dụ: stu725105088@hnue.edu.vn).'


def verify_email(backend, details, *args, **kwargs):
    email = (details.get('email') or '').strip().lower()
    if not email:
        raise InvalidEmail(backend)

    # Ràng buộc chỉ chấp nhận Email sinh viên HNUE (dạng stu<9 chữ số>@hnue.edu.vn hoặc domain @hnue.edu.vn)
    if not re.match(r'^stu\d{9}@hnue\.edu\.vn$', email, re.IGNORECASE) and not email.endswith('@hnue.edu.vn'):
        raise InvalidHNUEEmail(backend, email)


class SocialPostAuthForm(forms.Form):
    username = forms.RegexField(regex=re.compile(r'^\w+$', re.ASCII), max_length=30, label='Username',
                                error_messages={'invalid': 'A username must contain letters, numbers, or underscores.'})
    password = forms.CharField(label='Password', strip=False, widget=forms.PasswordInput(),
                               help_text=password_validation.password_validators_help_text_html(),
                               validators=[password_validation.validate_password])
    password_confirm = forms.CharField(label='Retype password', widget=forms.PasswordInput(), strip=False)

    def __init__(self, *args, lock_username=False, **kwargs):
        super().__init__(*args, **kwargs)
        if lock_username:
            self.fields['username'].widget.attrs.update({
                'readonly': 'readonly',
                'style': 'background-color: #f3f4f6; cursor: not-allowed; font-weight: 600;',
            })
            self.fields['username'].help_text = 'Username mặc định được khởi tạo từ Email và không thể thay đổi.'

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Tên đăng nhập này đã được sử dụng.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Passwords didn't match")


@partial
def get_username_password(backend, user, details=None, username=None, *args, **kwargs):
    if not user:
        request = backend.strategy.request

        # Xử lý tự động lấy username mặc định từ email nếu chưa truyền
        if not username and details and details.get('email'):
            email_prefix = details['email'].split('@')[0]
            username = slugify_username(email_prefix)

        # Đảm bảo username mặc định là duy nhất
        if username:
            base_username = username
            count = 1
            while User.objects.filter(username=username).exists():
                username = f'{base_username}_{count}'
                count += 1

        if request.POST:
            post_data = request.POST.copy()
            # Bắt buộc khóa username mặc định, không cho phép thay đổi từ phía client
            if username:
                post_data['username'] = username

            form = SocialPostAuthForm(post_data, lock_username=True)
            if form.is_valid():
                return {'username': form.cleaned_data['username'],
                        'password': form.cleaned_data['password']}
        else:
            form = SocialPostAuthForm(initial={'username': username}, lock_username=True)

        return render(request, 'registration/username_select.html', {
            'title': 'Hoàn tất thiết lập tài khoản',
            'form': form,
            'default_username': username,
        })



def add_password(user, password=None, *args, **kwargs):
    if password:
        user.set_password(password)
        user.save()


@partial
def make_profile(backend, user, response, is_new=False, *args, **kwargs):
    if is_new:
        if not hasattr(user, 'profile'):
            profile = Profile(user=user)
            profile.language = Language.get_default_language()
            logger.info('Info from %s: %s', backend.name, response)
            profile.save()
            form = ProfileForm(instance=profile, user=user)
        else:
            data = backend.strategy.request_data()
            logger.info(data)
            form = ProfileForm(data, instance=user.profile, user=user)
            if form.is_valid():
                with revisions.create_revision(atomic=True):
                    form.save()
                    revisions.set_user(user)
                    revisions.set_comment('Updated on registration')
                    return
        return render(backend.strategy.request, 'registration/profile_creation.html', {
            'title': 'Create your profile', 'form': form,
        })


class SocialAuthExceptionMiddleware(OldSocialAuthExceptionMiddleware):
    def process_exception(self, request, exception):
        if isinstance(exception, SocialAuthBaseException):
            return HttpResponseRedirect('%s?message=%s' % (reverse('social_auth_error'),
                                                           quote(self.get_message(request, exception))))
