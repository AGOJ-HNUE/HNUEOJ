import random
import re
import string
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import CASCADE, SET_NULL, Avg, Count, Max, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from judge.models.problem import Problem
from judge.models.profile import Profile

__all__ = [
    'Course',
    'Chapter',
    'Lesson',
    'LessonProblem',
    'Exam',
    'ExamProblem',
    'LessonProgress',
    'Enrollment',
    'Certificate',
]


class Course(models.Model):
    STATUS_DRAFT = 'DRAFT'
    STATUS_PUBLISHED = 'PUBLISHED'
    STATUS_ARCHIVED = 'ARCHIVED'
    STATUS_CHOICES = (
        (STATUS_DRAFT, _('Bản nháp')),
        (STATUS_PUBLISHED, _('Đã xuất bản')),
        (STATUS_ARCHIVED, _('Lưu trữ')),
    )

    key = models.SlugField(
        max_length=64,
        unique=True,
        verbose_name=_('Mã khóa học / Slug'),
        validators=[RegexValidator(r'^[a-z0-9-]+$', _('Chỉ chấp nhận chữ thường, số và dấu gạch ngang.'))],
    )
    title = models.CharField(max_length=255, verbose_name=_('Tên khóa học'), db_index=True)
    description = models.TextField(verbose_name=_('Mô tả khóa học'), blank=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name=_('Trạng thái'),
        db_index=True,
    )
    instructor = models.ForeignKey(
        Profile,
        verbose_name=_('Giảng viên'),
        related_name='instructed_courses',
        on_delete=CASCADE,
    )
    is_public = models.BooleanField(
        default=True,
        verbose_name=_('Hiển thị công khai'),
        help_text=_('Cho phép mọi học viên tìm kiếm và xem đề cương khóa học.'),
    )
    price = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Học phí (VNĐ)'),
        help_text=_('Học phí của khóa học (0 đồng là Miễn phí).'),
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name=_('Khóa khóa học'),
        help_text=_('Khi khóa, học viên không thể truy cập học hay làm bài.'),
    )
    allow_self_enrollment = models.BooleanField(
        default=True,
        verbose_name=_('Cho phép tự đăng ký'),
        help_text=_('Cho phép học viên tự bấm Đăng ký. Nếu tắt, chỉ giảng viên mới có thể thêm học viên.'),
        db_index=True,
    )
    validity_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Thời hạn học (ngày)'),
        help_text=_('Thời gian học tính bằng ngày kể từ mốc ghi danh. Để trống nếu không giới hạn.'),
    )
    REG_STATUS_OPEN = 'OPEN'
    REG_STATUS_UPCOMING = 'UPCOMING'
    REG_STATUS_CLOSED = 'CLOSED'
    REG_STATUS_CHOICES = (
        (REG_STATUS_OPEN, _('Đang mở đăng ký')),
        (REG_STATUS_UPCOMING, _('Sắp khai giảng')),
        (REG_STATUS_CLOSED, _('Hết chỗ / Đóng đăng ký')),
    )

    reg_status = models.CharField(
        max_length=16,
        choices=REG_STATUS_CHOICES,
        default=REG_STATUS_OPEN,
        verbose_name=_('Trạng thái tuyển sinh'),
        db_index=True,
    )
    target_audience = models.CharField(
        max_length=128,
        default='Khối THPT',
        blank=True,
        verbose_name=_('Đối tượng / Khối lớp'),
    )
    schedule_info = models.CharField(
        max_length=255,
        default='Tối T3, T5 (19h30 - 21h30)',
        blank=True,
        verbose_name=_('Lịch học'),
    )
    format_type = models.CharField(
        max_length=64,
        default='Online qua Zoom',
        blank=True,
        verbose_name=_('Hình thức học'),
    )
    duration_info = models.CharField(
        max_length=128,
        default='12 tuần (24 buổi)',
        blank=True,
        verbose_name=_('Thời lượng học'),
    )
    start_date_info = models.CharField(
        max_length=128,
        default='15/09/2026',
        blank=True,
        verbose_name=_('Ngày khai giảng'),
    )
    contact_url = models.CharField(
        max_length=512,
        default='',
        blank=True,
        verbose_name=_('Link Facebook / Tư vấn đăng ký'),
        help_text=_('Đường dẫn mở khi học viên bấm "Liên hệ đăng ký" (cho khóa học tốn phí).'),
    )

    thumbnail_url = models.CharField(
        max_length=255,
        verbose_name=_('Ảnh bìa khóa học'),
        blank=True,
        default='',
    )
    order_index = models.PositiveIntegerField(default=0, verbose_name=_('Thứ tự sắp xếp'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Ngày tạo'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Ngày cập nhật'))

    class Meta:
        verbose_name = _('Khóa học')
        verbose_name_plural = _('Các khóa học')
        ordering = ('order_index', '-created_at')

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('course_detail', args=[self.key])

    def is_accessible_by(self, user):
        if not user.is_authenticated:
            return self.status == self.STATUS_PUBLISHED and self.is_public
        if user.is_superuser or user.has_perm('judge.edit_all_course'):
            return True
        profile = getattr(user, 'profile', None)
        profile_id = profile.id if profile else None
        if profile_id and self.instructor_id == profile_id:
            return True
        if self.status == self.STATUS_PUBLISHED:
            return True
        if profile_id:
            return self.enrollments.filter(user_id=profile_id).exists()
        return False

    def is_editable_by(self, user):
        if not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff or user.has_perm('judge.edit_all_course'):
            return True
        profile = getattr(user, 'profile', None)
        return bool(profile and self.instructor_id == profile.id)

    def is_enrolled(self, user):
        if not user.is_authenticated:
            return False
        profile = getattr(user, 'profile', None)
        if not profile:
            return False
        enrollment = self.enrollments.filter(user_id=profile.id).first()
        if not enrollment:
            return False
        return not enrollment.is_expired

    def get_enrollment(self, user):
        if not user.is_authenticated:
            return None
        profile = getattr(user, 'profile', None)
        if not profile:
            return None
        return self.enrollments.filter(user_id=profile.id).first()

    @property
    def is_free(self):
        return self.price == 0

    @property
    def is_paid(self):
        return self.price > 0

    @property
    def formatted_price(self):
        if self.price == 0:
            return _('Miễn phí')
        return f'{self.price:,.0f} đ'.replace(',', '.')

    @property
    def reg_status_display(self):
        return dict(self.REG_STATUS_CHOICES).get(self.reg_status, _('Đang mở đăng ký'))

    @property
    def reg_status_badge_class(self):
        if self.reg_status == self.REG_STATUS_UPCOMING:
            return 'status-upcoming'
        elif self.reg_status == self.REG_STATUS_CLOSED:
            return 'status-closed'
        return 'status-open'

    @property
    def effective_contact_url(self):
        if self.contact_url:
            return self.contact_url
        return 'https://facebook.com'

    @property
    def instructor_name(self):
        if self.instructor_id and self.instructor and getattr(self.instructor, 'user', None):
            return getattr(self.instructor, 'display_name', '') or self.instructor.user.get_full_name() or self.instructor.user.username
        return _('Ban Chuyên môn VNOJ')

    @property
    def instructor_initial(self):
        name = self.instructor_name
        return str(name).strip()[0].upper() if name else 'V'

    @cached_property
    def total_lessons_count(self):
        return Lesson.objects.filter(chapter__course=self, is_published=True).count()

    @cached_property
    def total_exams_count(self):
        return Exam.objects.filter(course=self, is_published=True).count()

    @cached_property
    def student_count(self):
        return self.enrollments.count()


class Chapter(models.Model):
    course = models.ForeignKey(
        Course,
        verbose_name=_('Khóa học'),
        related_name='chapters',
        on_delete=CASCADE,
    )
    title = models.CharField(max_length=255, verbose_name=_('Tên chương'))
    description = models.TextField(verbose_name=_('Mô tả chương'), blank=True)
    order_index = models.PositiveIntegerField(default=0, verbose_name=_('Thứ tự'), db_index=True)

    class Meta:
        verbose_name = _('Chương học')
        verbose_name_plural = _('Các chương học')
        ordering = ('order_index', 'id')

    def __str__(self):
        return f'{self.course.title} - {self.title}'


class Lesson(models.Model):
    chapter = models.ForeignKey(
        Chapter,
        verbose_name=_('Chương'),
        related_name='lessons',
        on_delete=CASCADE,
    )
    title = models.CharField(max_length=255, verbose_name=_('Tiêu đề bài học'))
    content = models.TextField(verbose_name=_('Nội dung bài học (Markdown / HTML)'), blank=True)
    video_url = models.URLField(verbose_name=_('Link video bài giảng'), blank=True, null=True)
    order_index = models.PositiveIntegerField(default=0, verbose_name=_('Thứ tự'), db_index=True)
    is_published = models.BooleanField(default=True, verbose_name=_('Đã xuất bản'))
    is_locked = models.BooleanField(
        default=False,
        verbose_name=_('Khóa bài học'),
        help_text=_('Khi khóa, chỉ giáo viên mới có thể xem, học viên không thể truy cập.'),
    )
    estimated_minutes = models.PositiveIntegerField(default=15, verbose_name=_('Thời lượng ước tính (phút)'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Ngày tạo'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Ngày cập nhật'))

    class Meta:
        verbose_name = _('Bài học lý thuyết')
        verbose_name_plural = _('Các bài học lý thuyết')
        ordering = ('order_index', 'id')

    def __str__(self):
        return f'{self.chapter.title} - {self.title}'

    def get_absolute_url(self):
        return reverse('course_lesson', args=[self.chapter.course.key, self.id])

    def is_accessible_by(self, user):
        if not user.is_authenticated:
            return False
        if user.is_superuser or user.has_perm('judge.edit_all_course'):
            return True
        profile = getattr(user, 'profile', None)
        if profile and self.chapter.course.instructor_id == profile.id:
            return True
        if self.is_locked or not self.is_published:
            return False
        if self.chapter.course.is_locked:
            return False
        return self.chapter.course.is_enrolled(user)

    def is_completed_by(self, user):
        if not user.is_authenticated:
            return False
        return LessonProgress.objects.filter(user=user.profile, lesson=self, is_completed=True).exists()

    def get_practice_problems(self):
        return self.lesson_problems.select_related('problem').all()

    def has_required_problems(self):
        return self.lesson_problems.filter(is_required_for_completion=True).exists()

    def are_required_problems_completed_by(self, user):
        if not user.is_authenticated:
            return False
        required_problems = self.lesson_problems.filter(is_required_for_completion=True).select_related('problem')
        if not required_problems.exists():
            return True
        from judge.models.submission import Submission
        for lp in required_problems:
            ac_exists = Submission.objects.filter(
                user=user.profile,
                problem=lp.problem,
                result='AC',
            ).exists()
            if not ac_exists:
                return False
        return True

    def can_be_marked_completed_by(self, user):
        if not user.is_authenticated:
            return False
        return self.are_required_problems_completed_by(user)

    @property
    def embed_video_url(self):
        if not self.video_url:
            return ''
        url = self.video_url.strip()
        # YouTube: standard watch, short URL, shorts, live, embed
        yt_match = re.search(r'(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/|live\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
        if yt_match:
            video_id = yt_match.group(1)
            return f'https://www.youtube.com/embed/{video_id}'

        # Vimeo
        vimeo_match = re.search(r'vimeo\.com\/(?:video\/)?([0-9]+)', url)
        if vimeo_match:
            video_id = vimeo_match.group(1)
            return f'https://player.vimeo.com/video/{video_id}'

        # Google Drive
        drive_match = re.search(r'drive\.google\.com\/file\/d\/([a-zA-Z0-9_-]+)', url)
        if drive_match:
            file_id = drive_match.group(1)
            return f'https://drive.google.com/file/d/{file_id}/preview'

        return url


class LessonProblem(models.Model):
    lesson = models.ForeignKey(
        Lesson,
        verbose_name=_('Bài học'),
        related_name='lesson_problems',
        on_delete=CASCADE,
    )
    problem = models.ForeignKey(
        Problem,
        verbose_name=_('Bài tập kho VNOJ'),
        related_name='problem_lessons',
        on_delete=CASCADE,
    )
    alias = models.CharField(
        max_length=255,
        verbose_name=_('Tên bài hiển thị tùy biến'),
        blank=True,
        help_text=_('Để trống nếu muốn sử dụng tên gốc của bài tập.'),
    )
    custom_score = models.FloatField(
        verbose_name=_('Điểm số tùy biến'),
        null=True,
        blank=True,
        help_text=_('Điểm tối đa cho bài tập trong khuôn khổ bài học này.'),
    )
    is_required_for_completion = models.BooleanField(
        default=False,
        verbose_name=_('Bắt buộc hoàn thành (AC)'),
        help_text=_('Nếu bật, học viên bắt buộc phải AC bài này mới có thể hoàn thành bài học.'),
    )
    order_index = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Thứ tự hiển thị'),
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Bài tập đính kèm bài học')
        verbose_name_plural = _('Các bài tập đính kèm bài học')
        ordering = ('order_index', 'id')
        unique_together = ('lesson', 'problem')

    def __str__(self):
        return f'{self.lesson.title} - {self.display_title}'

    @property
    def display_title(self):
        return self.alias if self.alias else self.problem.name

    @property
    def display_points(self):
        return self.custom_score if self.custom_score is not None else self.problem.points


class Exam(models.Model):
    TARGET_COURSE = 'COURSE'
    TARGET_CHAPTER = 'CHAPTER'
    TARGET_CHOICES = (
        (TARGET_COURSE, _('Khóa học (Cuối khóa)')),
        (TARGET_CHAPTER, _('Chương (Kiểm tra phần)')),
    )

    TYPE_PRACTICE = 'PRACTICE'
    TYPE_RATED = 'RATED'
    TYPE_CHOICES = (
        (TYPE_PRACTICE, _('Luyện tập (Không tính Rating)')),
        (TYPE_RATED, _('Tính Rating')),
    )

    title = models.CharField(max_length=255, verbose_name=_('Tên kỳ thi'))
    description = models.TextField(verbose_name=_('Mô tả / Quy chế thi'), blank=True)
    target_type = models.CharField(
        max_length=16,
        choices=TARGET_CHOICES,
        default=TARGET_CHAPTER,
        verbose_name=_('Cấp độ gắn kết'),
    )
    course = models.ForeignKey(
        Course,
        verbose_name=_('Khóa học'),
        related_name='exams',
        on_delete=CASCADE,
    )
    chapter = models.ForeignKey(
        Chapter,
        verbose_name=_('Chương'),
        related_name='exams',
        null=True,
        blank=True,
        on_delete=CASCADE,
    )
    contest = models.ForeignKey(
        'Contest',
        verbose_name=_('Kỳ thi liên kết (Tùy chọn)'),
        null=True,
        blank=True,
        on_delete=SET_NULL,
        related_name='course_exams',
    )
    problems = models.ManyToManyField(
        Problem,
        verbose_name=_('Bài tập'),
        through='ExamProblem',
        related_name='course_exams',
    )
    exam_type = models.CharField(
        max_length=16,
        choices=TYPE_CHOICES,
        default=TYPE_PRACTICE,
        verbose_name=_('Loại kỳ thi'),
    )
    start_time = models.DateTimeField(verbose_name=_('Thời gian bắt đầu'), null=True, blank=True)
    end_time = models.DateTimeField(verbose_name=_('Thời gian kết thúc'), null=True, blank=True)
    time_limit = models.DurationField(verbose_name=_('Thời lượng làm bài'), null=True, blank=True)
    order_index = models.PositiveIntegerField(default=0, verbose_name=_('Thứ tự'), db_index=True)
    pass_percentage = models.FloatField(default=60.0, verbose_name=_('Điểm đạt (%)'))
    is_published = models.BooleanField(default=True, verbose_name=_('Đã xuất bản'))
    is_locked = models.BooleanField(
        default=False,
        verbose_name=_('Khóa kỳ thi'),
        help_text=_('Khi khóa, chỉ giáo viên mới có thể xem, học viên không thể truy cập.'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Ngày tạo'))

    class Meta:
        verbose_name = _('Kỳ thi khóa học')
        verbose_name_plural = _('Các kỳ thi khóa học')
        ordering = ('order_index', 'id')

    def __str__(self):
        return f'{self.course.title} - {self.title}'

    def get_absolute_url(self):
        return reverse('course_exam', args=[self.course.key, self.id])

    @property
    def is_active(self):
        now = timezone.now()
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
        return True

    def can_access(self, user):
        if not user.is_authenticated:
            return False
        if user.is_superuser or user.has_perm('judge.edit_all_course'):
            return True
        profile = getattr(user, 'profile', None)
        if profile and self.course.instructor_id == profile.id:
            return True
        if self.is_locked or not self.is_published:
            return False
        if self.course.is_locked:
            return False
        if not profile:
            return False
        enrollment = self.course.enrollments.filter(user_id=profile.id).first()
        if not enrollment or enrollment.is_expired:
            return False
        return True

    def get_user_score(self, user):
        """Tính điểm tổng của học viên trên kỳ thi này"""
        if not user.is_authenticated:
            return 0, 0
        from judge.models.submission import Submission
        total_max_score = 0.0
        user_total_score = 0.0
        for ep in self.exam_problems.select_related('problem'):
            weight = ep.custom_score if ep.custom_score is not None else ep.problem.points
            total_max_score += weight
            best_sub = Submission.objects.filter(
                user_id=user.profile.id,
                problem_id=ep.problem_id,
                exam=self,
                points__isnull=False,
            ).order_by('-points').first()
            if best_sub and best_sub.points is not None:
                # scale to custom score if customized
                if ep.custom_score is not None and ep.problem.points:
                    scale = ep.custom_score / ep.problem.points
                    user_total_score += min(ep.custom_score, best_sub.points * scale)
                else:
                    user_total_score += best_sub.points

        def clean_val(v):
            r = round(float(v), 2)
            return int(r) if r.is_integer() else r

        return clean_val(user_total_score), clean_val(total_max_score)

    def is_passed_by(self, user):
        user_score, total_score = self.get_user_score(user)
        if total_score <= 0:
            return True
        pct = (user_score / total_score) * 100.0
        return pct >= self.pass_percentage


class ExamProblem(models.Model):
    exam = models.ForeignKey(
        Exam,
        verbose_name=_('Kỳ thi'),
        related_name='exam_problems',
        on_delete=CASCADE,
    )
    problem = models.ForeignKey(
        Problem,
        verbose_name=_('Bài tập gốc'),
        related_name='exam_problems',
        on_delete=CASCADE,
    )
    alias = models.CharField(
        max_length=255,
        verbose_name=_('Tên bài hiển thị tùy biến'),
        blank=True,
        help_text=_('Ghi đè tên hiển thị của bài tập trong kỳ thi.'),
    )
    custom_score = models.FloatField(
        verbose_name=_('Điểm số tùy biến'),
        null=True,
        blank=True,
        help_text=_('Ghi đè điểm tối đa của bài tập trong kỳ thi.'),
    )
    order_index = models.PositiveIntegerField(default=0, verbose_name=_('Thứ tự sắp xếp'), db_index=True)
    partial = models.BooleanField(default=True, verbose_name=_('Cho phép chấm điểm từng phần'))

    class Meta:
        verbose_name = _('Bài tập trong kỳ thi')
        verbose_name_plural = _('Các bài tập trong kỳ thi')
        unique_together = ('exam', 'problem')
        ordering = ('order_index', 'id')

    def __str__(self):
        return f'{self.exam.title} - {self.display_title}'

    @property
    def display_title(self):
        return self.alias if self.alias else self.problem.name

    @property
    def display_points(self):
        return self.custom_score if self.custom_score is not None else self.problem.points


class LessonProgress(models.Model):
    user = models.ForeignKey(
        Profile,
        verbose_name=_('Học viên'),
        related_name='lesson_progresses',
        on_delete=CASCADE,
    )
    lesson = models.ForeignKey(
        Lesson,
        verbose_name=_('Bài học'),
        related_name='progresses',
        on_delete=CASCADE,
    )
    is_completed = models.BooleanField(default=False, verbose_name=_('Đã hoàn thành'))
    completed_at = models.DateTimeField(verbose_name=_('Thời điểm hoàn thành'), null=True, blank=True)

    class Meta:
        verbose_name = _('Tiến độ bài học')
        verbose_name_plural = _('Tiến độ bài học')
        unique_together = ('user', 'lesson')
        indexes = [
            models.Index(fields=['user', 'lesson']),
        ]

    def __str__(self):
        return f'{self.user.user.username} - {self.lesson.title} ({"Done" if self.is_completed else "Pending"})'


class Enrollment(models.Model):
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_READY_FOR_REVIEW = 'READY_FOR_REVIEW'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_DROPPED = 'DROPPED'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_CHOICES = (
        (STATUS_ACTIVE, _('Đang học')),
        (STATUS_READY_FOR_REVIEW, _('Chờ duyệt cấp chứng chỉ')),
        (STATUS_COMPLETED, _('Đã hoàn thành / Nhận chứng chỉ')),
        (STATUS_DROPPED, _('Đã hủy')),
        (STATUS_EXPIRED, _('Đã hết hạn')),
    )

    user = models.ForeignKey(
        Profile,
        verbose_name=_('Học viên'),
        related_name='course_enrollments',
        on_delete=CASCADE,
    )
    course = models.ForeignKey(
        Course,
        verbose_name=_('Khóa học'),
        related_name='enrollments',
        on_delete=CASCADE,
    )
    progress_percentage = models.FloatField(default=0.0, verbose_name=_('Tiến độ (%)'))
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        verbose_name=_('Trạng thái'),
        db_index=True,
    )
    enrolled_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Ngày ghi danh'))
    expiry_date = models.DateTimeField(null=True, blank=True, verbose_name=_('Ngày hết hạn truy cập'), db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Ngày hoàn thành'))
    last_accessed_at = models.DateTimeField(auto_now=True, verbose_name=_('Truy cập gần nhất'))

    @property
    def is_expired(self):
        if self.expiry_date is None:
            return False
        return timezone.now() > self.expiry_date

    class Meta:
        verbose_name = _('Ghi danh khóa học')
        verbose_name_plural = _('Danh sách ghi danh')
        unique_together = ('user', 'course')
        indexes = [
            models.Index(fields=['course', 'status']),
            models.Index(fields=['user', 'course']),
        ]

    def __str__(self):
        return f'{self.user.user.username} -> {self.course.title} ({self.progress_percentage:.1f}%)'

    def recalculate_progress(self):
        """Tính toán lại % tiến độ và cập nhật trạng thái nếu đạt 100%"""
        total_lessons = Lesson.objects.filter(chapter__course=self.course, is_published=True).count()
        total_exams = Exam.objects.filter(course=self.course, is_published=True).count()
        total_items = total_lessons + total_exams

        if total_items == 0:
            self.progress_percentage = 100.0
            if self.status == self.STATUS_ACTIVE:
                self.status = self.STATUS_READY_FOR_REVIEW
            self.save(update_fields=['progress_percentage', 'status'])
            return self.progress_percentage

        completed_lessons = LessonProgress.objects.filter(
            user=self.user,
            lesson__chapter__course=self.course,
            lesson__is_published=True,
            is_completed=True,
        ).count()

        passed_exams = 0
        for exam in Exam.objects.filter(course=self.course, is_published=True):
            if exam.is_passed_by(self.user.user):
                passed_exams += 1

        completed_items = completed_lessons + passed_exams
        self.progress_percentage = min(100.0, round((completed_items / total_items) * 100.0, 1))

        if self.progress_percentage >= 100.0:
            if self.status == self.STATUS_ACTIVE:
                self.status = self.STATUS_READY_FOR_REVIEW
        elif self.status == self.STATUS_READY_FOR_REVIEW:
            self.status = self.STATUS_ACTIVE

        self.save(update_fields=['progress_percentage', 'status'])
        return self.progress_percentage


class Certificate(models.Model):
    cert_code = models.CharField(
        max_length=64,
        unique=True,
        verbose_name=_('Mã chứng chỉ'),
        db_index=True,
    )
    user = models.ForeignKey(
        Profile,
        verbose_name=_('Học viên'),
        related_name='certificates',
        on_delete=CASCADE,
    )
    course = models.ForeignKey(
        Course,
        verbose_name=_('Khóa học'),
        related_name='issued_certificates',
        on_delete=CASCADE,
    )
    issued_by = models.ForeignKey(
        Profile,
        verbose_name=_('Giảng viên cấp'),
        related_name='authorized_certificates',
        on_delete=SET_NULL,
        null=True,
    )
    issued_date = models.DateTimeField(default=timezone.now, verbose_name=_('Ngày cấp'))
    grade = models.CharField(max_length=50, default='Xuất sắc', verbose_name=_('Xếp loại'))
    verification_url = models.URLField(blank=True, verbose_name=_('Đường dẫn xác thực'))

    class Meta:
        verbose_name = _('Chứng chỉ')
        verbose_name_plural = _('Danh sách chứng chỉ')
        unique_together = ('user', 'course')
        ordering = ('-issued_date',)

    def __str__(self):
        return f'{self.cert_code} - {self.user.user.username} ({self.course.title})'

    def get_absolute_url(self):
        return reverse('certificate_detail', args=[self.cert_code])

    @classmethod
    def generate_cert_code(cls, course_id, user_id):
        now_str = timezone.now().strftime('%Y%m')
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f'VNOJ-CERT-{now_str}-C{course_id}U{user_id}-{random_suffix}'

    def save(self, *args, **kwargs):
        if not self.cert_code:
            self.cert_code = self.generate_cert_code(self.course_id, self.user_id)
        if not self.verification_url:
            self.verification_url = f'/certificate/{self.cert_code}/'
        super().save(*args, **kwargs)
