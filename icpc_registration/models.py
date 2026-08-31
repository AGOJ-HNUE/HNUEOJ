from django.conf import settings
from django.db import models


class ICPCRegistration(models.Model):
    EXPERIENCE_BEGINNER = 'beginner'
    EXPERIENCE_BASIC = 'basic'
    EXPERIENCE_INTERMEDIATE = 'intermediate'
    EXPERIENCE_ADVANCED = 'advanced'

    EXPERIENCE_CHOICES = [
        (EXPERIENCE_BEGINNER, 'Mới bắt đầu học lập trình'),
        (EXPERIENCE_BASIC, 'Đã nắm cơ bản (C++, Python, Pascal...)'),
        (EXPERIENCE_INTERMEDIATE, 'Đã học Cấu trúc dữ liệu & Thuật toán'),
        (EXPERIENCE_ADVANCED, 'Đã tham gia đội tuyển / HSG / Olympic / ICPC'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Chờ duyệt'),
        (STATUS_APPROVED, 'Đã duyệt'),
        (STATUS_REJECTED, 'Từ chối'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='icpc_registrations',
        verbose_name='Tài khoản HNUEOJ',
    )
    full_name = models.CharField(max_length=150, verbose_name='Họ và tên')
    student_id = models.CharField(max_length=50, verbose_name='Mã sinh viên')
    academic_class = models.CharField(max_length=100, verbose_name='Lớp')
    cohort = models.CharField(max_length=50, verbose_name='Khóa (ví dụ: K73, K74, K75...)')
    email = models.EmailField(verbose_name='Email')
    phone = models.CharField(max_length=20, verbose_name='Số điện thoại (Zalo)')
    facebook_url = models.CharField(max_length=255, blank=True, verbose_name='Link Facebook')
    programming_experience = models.CharField(
        max_length=50,
        choices=EXPERIENCE_CHOICES,
        default=EXPERIENCE_BEGINNER,
        verbose_name='Trình độ lập trình',
    )
    achievements = models.TextField(
        blank=True,
        verbose_name='Thành tích / Kinh nghiệm / Giải thưởng đã đạt được',
    )
    reason = models.TextField(verbose_name='Lý do & Mục tiêu tham gia')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='Trạng thái duyệt',
    )
    admin_note = models.TextField(blank=True, verbose_name='Ghi chú của Admin')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời gian đăng ký')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Cập nhật lần cuối')

    class Meta:
        verbose_name = 'Đơn đăng ký ICPC'
        verbose_name_plural = 'Danh sách đơn đăng ký ICPC'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} ({self.student_id}) - {self.academic_class}"
