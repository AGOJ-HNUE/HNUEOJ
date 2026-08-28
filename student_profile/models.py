from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Semester(models.Model):
    id = models.CharField(max_length=50, primary_key=True, help_text=_("Mã học kỳ (VD: 2025_2026_HK1, sem_1, ...)"))
    name = models.CharField(max_length=120, verbose_name=_("Tên học kỳ"))
    academic_year = models.CharField(max_length=30, default="2025-2026", verbose_name=_("Năm học"))
    order = models.PositiveSmallIntegerField(default=1, verbose_name=_("Thứ tự kỳ"))
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='custom_semesters',
        verbose_name=_("Người tạo (null nếu là kỳ mặc định)")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Học kỳ")
        verbose_name_plural = _("Danh sách học kỳ")
        ordering = ['academic_year', 'order', 'created_at']

    def __str__(self):
        return f"{self.name} ({self.academic_year})"


class Subject(models.Model):
    code = models.CharField(max_length=50, primary_key=True, verbose_name=_("Mã học phần"))
    name = models.CharField(max_length=255, verbose_name=_("Tên môn học"))
    credits = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        verbose_name=_("Số tín chỉ")
    )
    difficulty = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name=_("Độ khó môn học (1-10)")
    )
    department = models.CharField(max_length=150, blank=True, null=True, verbose_name=_("Khoa / Bộ môn"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Môn học")
        verbose_name_plural = _("Danh mục môn học")
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name} ({self.credits} TC)"


class StudentGrade(models.Model):
    GRADE_CHOICES = [
        ('A+', 'A+ (4.0)'),
        ('A', 'A (3.7 / 4.0)'),
        ('B+', 'B+ (3.5)'),
        ('B', 'B (3.0)'),
        ('C+', 'C+ (2.5)'),
        ('C', 'C (2.0)'),
        ('D+', 'D+ (1.5)'),
        ('D', 'D (1.0)'),
        ('F', 'F (0.0)'),
    ]

    GRADE_SCALE_MAP = {
        'A+': Decimal('4.0'),
        'A': Decimal('3.7'),  # Hoặc 4.0 tùy scale (client có thể truyền score_4)
        'B+': Decimal('3.5'),
        'B': Decimal('3.0'),
        'C+': Decimal('2.5'),
        'C': Decimal('2.0'),
        'D+': Decimal('1.5'),
        'D': Decimal('1.0'),
        'F': Decimal('0.0'),
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='academic_grades',
        verbose_name=_("Tài khoản sinh viên")
    )
    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        related_name='grades',
        verbose_name=_("Học kỳ")
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='student_grades',
        verbose_name=_("Môn học")
    )
    letter_grade = models.CharField(max_length=5, choices=GRADE_CHOICES, blank=True, null=True, verbose_name=_("Điểm hiện tại"))
    improvement_grade = models.CharField(max_length=5, blank=True, null=True, verbose_name=_("Điểm cải thiện"))
    target_grade = models.CharField(max_length=5, blank=True, null=True, verbose_name=_("Mục tiêu"))
    score_4 = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0.0'), verbose_name=_("Điểm hệ 4"))
    notes = models.TextField(blank=True, null=True, verbose_name=_("Ghi chú"))
    order = models.PositiveIntegerField(default=0, verbose_name=_("Thứ tự hiển thị"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Điểm sinh viên")
        verbose_name_plural = _("Bảng điểm sinh viên")
        unique_together = ('user', 'semester', 'subject')
        ordering = ['semester__academic_year', 'semester__order', 'order', 'created_at']

    @property
    def effective_letter_grade(self):
        """Nếu có điểm cải thiện thì ưu tiên điểm cải thiện"""
        return self.improvement_grade or self.letter_grade

    @property
    def is_passed(self):
        grade = self.effective_letter_grade
        return grade and grade != 'F'

    def __str__(self):
        return f"{self.user.username} - {self.subject.code}: {self.letter_grade}"
