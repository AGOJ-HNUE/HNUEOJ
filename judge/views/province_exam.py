from django.db.models import Q
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView

from judge.models.province_exam import (
    PROVINCE_CHOICES,
    PROVINCE_DICT,
    PROVINCE_EXAM_CATEGORY_CHOICES,
    PROVINCE_EXAM_CATEGORY_DICT,
    ProvinceExam,
)
from judge.utils.views import TitleMixin, paginate_query_context

__all__ = ['ProvinceExamList']


class ProvinceExamList(TitleMixin, ListView):
    model = ProvinceExam
    template_name = 'contest/province_list.html'
    context_object_name = 'exam_list'
    title = _('Kho lưu trữ Đề thi Các Tỉnh / Thành phố Việt Nam')
    paginate_by = 24

    @cached_property
    def _now(self):
        return timezone.now()

    def get_queryset(self):
        self.search_query = None
        qs = ProvinceExam.objects.select_related('contest').filter(is_visible=True)

        # Search filter
        if 'search' in self.request.GET:
            self.search_query = search = ' '.join(self.request.GET.getlist('search')).strip()
            if search:
                qs = qs.filter(
                    Q(name__icontains=search) |
                    Q(academic_year__icontains=search) |
                    Q(description__icontains=search) |
                    Q(contest__name__icontains=search)
                )

        # Province filter
        selected_province = self.request.GET.get('province', '').strip().upper()
        if selected_province:
            qs = qs.filter(province=selected_province)

        # Category filter (thpt, thcs, tieu_hoc, chuyen, olympic, hsgqg, other)
        selected_category = self.request.GET.get('category', '').strip().lower()
        if selected_category and selected_category in PROVINCE_EXAM_CATEGORY_DICT:
            qs = qs.filter(category=selected_category)

        # Academic year filter
        selected_year = self.request.GET.get('year', '').strip()
        if selected_year:
            qs = qs.filter(academic_year__icontains=selected_year)

        return qs.order_by('-order', '-academic_year', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        selected_province = self.request.GET.get('province', '').strip().upper()
        selected_category = self.request.GET.get('category', '').strip().lower()
        selected_year = self.request.GET.get('year', '').strip()

        # Available academic years for filtering
        years_list = list(
            ProvinceExam.objects.filter(is_visible=True)
            .values_list('academic_year', flat=True)
            .distinct()
        )
        years_list = sorted([y for y in set(years_list) if y], reverse=True)

        context['provinces'] = PROVINCE_CHOICES
        context['categories'] = PROVINCE_EXAM_CATEGORY_CHOICES
        context['years'] = years_list
        context['selected_province'] = selected_province
        context['selected_province_name'] = PROVINCE_DICT.get(selected_province, '')
        context['selected_category'] = selected_category
        context['selected_category_name'] = PROVINCE_EXAM_CATEGORY_DICT.get(selected_category, '')
        context['selected_year'] = selected_year
        context['search_query'] = self.search_query
        context['now'] = self._now
        context['first_page_href'] = '.'
        context['page_suffix'] = '#province-exams'
        context.update(paginate_query_context(self.request))
        return context
