from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from reversion.admin import VersionAdmin

from judge.models.province_exam import ProvinceExam


class ProvinceExamAdmin(VersionAdmin):
    list_display = (
        'name',
        'category_display',
        'province_display',
        'academic_year',
        'has_exam_url_display',
        'has_solution_url_display',
        'has_practice_url_display',
        'is_visible',
        'order',
        'created_at',
    )
    list_editable = ('is_visible', 'order')
    list_filter = ('is_visible', 'category', 'province', 'academic_year')
    search_fields = ('name', 'academic_year', 'description')
    raw_id_fields = ('contest',)
    ordering = ('-order', '-academic_year', '-created_at')

    fieldsets = (
        (_('Thông tin cơ bản'), {
            'fields': (
                'name',
                'category',
                'province',
                'academic_year',
                'is_visible',
                'order',
            )
        }),
        (_('Liên kết tài liệu & Luyện tập'), {
            'description': _('Các liên kết này sẽ được hiển thị dạng nút trên card đề thi nếu có giá trị.'),
            'fields': (
                'exam_url',
                'solution_url',
                'contest',
                'practice_url',
            )
        }),
        (_('Thông tin bổ sung'), {
            'fields': (
                'description',
            )
        }),
    )

    @admin.display(description=_('Cấp học / Loại đề'), ordering='category')
    def category_display(self, obj):
        cat_map = {
            'thpt': ('#dbeafe', '#1e40af'),
            'thcs': ('#e0e7ff', '#3730a3'),
            'chuyen': ('#fce7f3', '#9d174d'),
            'olympic': ('#fef08a', '#854d0e'),
            'hsgqg': ('#fee2e2', '#991b1b'),
        }
        bg, color = cat_map.get(obj.category, ('#f3f4f6', '#374151'))
        return format_html(
            '<span style="background: {}; color: {}; padding: 3px 8px; border-radius: 9999px; font-weight: 600; font-size: 0.78rem;">{}</span>',
            bg, color, obj.get_category_display()
        )

    @admin.display(description=_('Tỉnh / Thành'), ordering='province')
    def province_display(self, obj):
        val = obj.get_province_display() or _('Toàn quốc')
        return format_html(
            '<span style="font-weight: 500; color: #1e293b;"><i class="fa fa-map-marker" style="color: #ef4444; margin-right: 4px;"></i>{}</span>',
            val
        )

    @admin.display(description=_('Đề thi'), boolean=False)
    def has_exam_url_display(self, obj):
        if obj.exam_url:
            return format_html('<a href="{}" target="_blank" title="{}" style="color: #2563eb; font-weight: 600;"><i class="fa fa-file-pdf-o"></i> Link</a>', obj.exam_url, obj.exam_url)
        return format_html('<span style="color: #94a3b8;">—</span>')

    @admin.display(description=_('Lời giải / Test'), boolean=False)
    def has_solution_url_display(self, obj):
        if obj.solution_url:
            return format_html('<a href="{}" target="_blank" title="{}" style="color: #059669; font-weight: 600;"><i class="fa fa-check-circle"></i> Link</a>', obj.solution_url, obj.solution_url)
        return format_html('<span style="color: #94a3b8;">—</span>')

    @admin.display(description=_('Luyện tập'), boolean=False)
    def has_practice_url_display(self, obj):
        url = obj.effective_practice_url
        if url:
            title = obj.contest.name if obj.contest else url
            return format_html('<a href="{}" target="_blank" title="{}" style="color: #7c3aed; font-weight: 600;"><i class="fa fa-laptop"></i> Thi</a>', url, title)
        return format_html('<span style="color: #94a3b8;">—</span>')
