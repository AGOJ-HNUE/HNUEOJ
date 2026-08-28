from django.db import models
from django.utils.translation import gettext_lazy as _

PROVINCE_CHOICES = (
    ('ALL', _('Toàn quốc')),
    ('AG', _('An Giang')),
    ('BV', _('Bà Rịa - Vũng Tàu')),
    ('BL', _('Bạc Liêu')),
    ('BG', _('Bắc Giang')),
    ('BK', _('Bắc Kạn')),
    ('BN', _('Bắc Ninh')),
    ('BTR', _('Bến Tre')),
    ('BD', _('Bình Định')),
    ('BDU', _('Bình Dương')),
    ('BP', _('Bình Phước')),
    ('BT', _('Bình Thuận')),
    ('CM', _('Cà Mau')),
    ('CT', _('Cần Thơ')),
    ('CB', _('Cao Bằng')),
    ('DN', _('Đà Nẵng')),
    ('DL', _('Đắk Lắk')),
    ('DNO', _('Đắk Nông')),
    ('DB', _('Điện Biên')),
    ('DNA', _('Đồng Nai')),
    ('DT', _('Đồng Tháp')),
    ('GL', _('Gia Lai')),
    ('HG', _('Hà Giang')),
    ('HNA', _('Hà Nam')),
    ('HN', _('Hà Nội')),
    ('HT', _('Hà Tĩnh')),
    ('HD', _('Hải Dương')),
    ('HP', _('Hải Phòng')),
    ('HGI', _('Hậu Giang')),
    ('HB', _('Hòa Bình')),
    ('HY', _('Hưng Yên')),
    ('KH', _('Khánh Hòa')),
    ('KG', _('Kiên Giang')),
    ('KT', _('Kon Tum')),
    ('LC', _('Lai Châu')),
    ('LD', _('Lâm Đồng')),
    ('LS', _('Lạng Sơn')),
    ('LCA', _('Lào Cai')),
    ('LA', _('Long An')),
    ('ND', _('Nam Định')),
    ('NA', _('Nghệ An')),
    ('NB', _('Ninh Bình')),
    ('NT', _('Ninh Thuận')),
    ('PT', _('Phú Thọ')),
    ('PY', _('Phú Yên')),
    ('QB', _('Quảng Bình')),
    ('QNA', _('Quảng Nam')),
    ('QNG', _('Quảng Ngãi')),
    ('QNI', _('Quảng Ninh')),
    ('QT', _('Quảng Trị')),
    ('ST', _('Sóc Trăng')),
    ('SL', _('Sơn La')),
    ('TN', _('Tây Ninh')),
    ('TB', _('Thái Bình')),
    ('TNG', _('Thái Nguyên')),
    ('TH', _('Thanh Hóa')),
    ('HUE', _('Thừa Thiên Huế')),
    ('TG', _('Tiền Giang')),
    ('HCM', _('TP. Hồ Chí Minh')),
    ('TV', _('Trà Vinh')),
    ('TQ', _('Tuyên Quang')),
    ('VL', _('Vĩnh Long')),
    ('VP', _('Vĩnh Phúc')),
    ('YB', _('Yên Bái')),
)

PROVINCE_DICT = dict(PROVINCE_CHOICES)

PROVINCE_EXAM_CATEGORY_CHOICES = (
    ('thpt', _('THPT')),
    ('thcs', _('THCS')),
    ('chuyen', _('Thi Chuyên')),
    ('olympic', _('Olympic / Trại hè')),
    ('hsgqg', _('Đội tuyển HSGQG')),
)

PROVINCE_EXAM_CATEGORY_DICT = dict(PROVINCE_EXAM_CATEGORY_CHOICES)

ACADEMIC_YEAR_CHOICES = (
    ('2026-2027', '2026-2027'),
    ('2025-2026', '2025-2026'),
    ('2024-2025', '2024-2025'),
    ('2023-2024', '2023-2024'),
    ('2022-2023', '2022-2023'),
    ('2021-2022', '2021-2022'),
    ('2020-2021', '2020-2021'),
    ('2019-2020', '2019-2020'),
)


class ProvinceExam(models.Model):
    name = models.CharField(
        max_length=255,
        verbose_name=_('Tên đề / Kỳ thi'),
        db_index=True,
        help_text=_('Ví dụ: Đề thi chọn HSG lớp 12 tỉnh Ninh Bình năm học 2025-2026')
    )
    category = models.CharField(
        max_length=20,
        choices=PROVINCE_EXAM_CATEGORY_CHOICES,
        default='thpt',
        verbose_name=_('Cấp học / Loại đề'),
        db_index=True
    )
    province = models.CharField(
        max_length=10,
        choices=PROVINCE_CHOICES,
        blank=True,
        default='',
        verbose_name=_('Tỉnh / Thành phố'),
        db_index=True
    )
    academic_year = models.CharField(
        max_length=16,
        verbose_name=_('Năm học'),
        db_index=True,
        help_text=_('Định dạng cụ thể: 2025-2026, 2024-2025, 2023-2024...')
    )
    exam_url = models.URLField(
        max_length=1000,
        blank=True,
        default='',
        verbose_name=_('Link đề thi (PDF / Drive)'),
        help_text=_('Đường dẫn tải hoặc xem trực tuyến file đề thi (PDF, Google Drive, OneDrive, v.v.).')
    )
    solution_url = models.URLField(
        max_length=1000,
        blank=True,
        default='',
        verbose_name=_('Link lời giải / Bộ test'),
        help_text=_('Đường dẫn tải hoặc xem đáp án, lời giải chi tiết, file test.')
    )
    contest = models.ForeignKey(
        'Contest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='province_exams',
        verbose_name=_('Kỳ thi luyện tập (Contest)'),
        help_text=_('Chọn Contest trên hệ thống để người học vào làm bài trực tiếp.')
    )
    practice_url = models.URLField(
        max_length=1000,
        blank=True,
        default='',
        verbose_name=_('Link luyện tập ngoài'),
        help_text=_('Đường dẫn luyện tập khác nếu không dùng Contest trên hệ thống.')
    )
    is_visible = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_('Hiển thị card'),
        help_text=_('Có hiển thị card này trên trang danh sách đề thi hay không (mặc định: Có).')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Ghi chú / Mô tả tóm tắt'),
        help_text=_('Thông tin thêm về cấu trúc đề, thang điểm, thời gian làm bài, v.v.')
    )
    order = models.IntegerField(
        default=0,
        verbose_name=_('Thứ tự ưu tiên'),
        help_text=_('Số càng lớn sẽ được ưu tiên hiển thị trước.')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_('Thời gian tạo')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Cập nhật lần cuối')
    )

    class Meta:
        verbose_name = _('Đề thi Tỉnh / Thành phố')
        verbose_name_plural = _('Kho lưu trữ Đề thi Tỉnh / Thành phố')
        ordering = ['-order', '-academic_year', '-created_at']

    def __str__(self):
        prov = self.get_province_display() or _('Toàn quốc')
        return f"[{prov}] {self.name} ({self.academic_year})"

    @property
    def effective_practice_url(self):
        if self.contest:
            return self.contest.get_absolute_url()
        return self.practice_url
