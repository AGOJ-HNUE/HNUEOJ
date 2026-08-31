import json
import re
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.db.models import Count, Max, Q
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import _json_script_escapes
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from judge import event_poster as event
from judge.judgeapi import judge_submission
from judge.models import Certificate, Chapter, Contest, ContestParticipation, Course, CourseContest, Enrollment, Exam, ExamProblem, \
    Language, Lesson, LessonProblem, LessonProgress, Organization, Problem, Profile, Submission, SubmissionSource
from judge.utils.views import TitleMixin
from judge.views.contests import CreateContest, EditContest
from judge.views.problem import ProblemSubmitForm, ProblemSubmitMixin


class CourseListView(TitleMixin, ListView):
    model = Course
    template_name = 'course/course_list.html'
    context_object_name = 'courses'
    paginate_by = 12

    def get_title(self):
        return _('Cổng Đào tạo & Khóa học Trực tuyến - LMS HNUEOJ')

    def get_queryset(self):
        user = self.request.user
        tab = self.request.GET.get('tab', 'all')
        qs = Course.objects.filter(is_public=True, status=Course.STATUS_PUBLISHED)

        if user.is_authenticated:
            if tab == 'enrolled':
                qs = Course.objects.filter(enrollments__user=user.profile)
            elif tab == 'teaching':
                qs = Course.objects.filter(instructor=user.profile)
            elif user.is_superuser or user.has_perm('judge.edit_all_course'):
                if tab == 'all':
                    qs = Course.objects.all()

        if tab == 'thcs':
            qs = qs.filter(Q(target_audience__icontains='THCS') | Q(title__icontains='THCS'))
        elif tab == 'thpt':
            qs = qs.filter(Q(target_audience__icontains='THPT') | Q(title__icontains='THPT'))
        elif tab == 'chuyen':
            qs = qs.filter(Q(target_audience__icontains='Chuyên') | Q(target_audience__icontains='Đội tuyển') | Q(title__icontains='Chuyên') | Q(title__icontains='HSG'))
        elif tab == 'online':
            qs = qs.filter(format_type__icontains='Online')
        elif tab == 'offline':
            qs = qs.filter(Q(format_type__icontains='Trực tiếp') | Q(format_type__icontains='Offline'))

        query = self.request.GET.get('q', '').strip()
        if query:
            qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(target_audience__icontains=query))

        return qs.select_related('instructor__user').prefetch_related('enrollments')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['current_tab'] = self.request.GET.get('tab', 'all')
        context['search_query'] = self.request.GET.get('q', '')

        if user.is_authenticated:
            context['enrolled_count'] = Enrollment.objects.filter(user=user.profile).count()
            context['teaching_count'] = Course.objects.filter(instructor=user.profile).count()
            # Map of course_id -> enrollment
            enrollments = Enrollment.objects.filter(user=user.profile)
            context['user_enrollments'] = {e.course_id: e for e in enrollments}
        else:
            context['enrolled_count'] = 0
            context['teaching_count'] = 0
            context['user_enrollments'] = {}

        return context


class CourseDetailView(TitleMixin, DetailView):
    model = Course
    slug_field = 'key'
    slug_url_kwarg = 'slug'
    template_name = 'course/course_detail.html'
    context_object_name = 'course'

    def get_title(self):
        return f'{self.object.title} - LMS HNUEOJ'

    def get_object(self, queryset=None):
        course = super().get_object(queryset)
        if not course.is_accessible_by(self.request.user):
            raise Http404(_('Khóa học không tồn tại hoặc bạn không có quyền truy cập.'))
        return course

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        user = self.request.user

        chapters = course.chapters.prefetch_related('lessons', 'chapter_contests__contest', 'exams').all()
        context['chapters'] = chapters
        context['course_contests'] = course.course_contests.filter(scope_type=CourseContest.SCOPE_COURSE).select_related('contest')
        context['course_exams'] = course.exams.filter(target_type=Exam.TARGET_COURSE, is_published=True)

        first_lesson = None
        for ch in chapters:
            for l in ch.lessons.all():
                if l.is_published:
                    first_lesson = l
                    break
            if first_lesson:
                break
        context['first_lesson'] = first_lesson

        if user.is_authenticated:
            enrollment = course.get_enrollment(user)
            context['enrollment'] = enrollment
            context['is_instructor'] = course.is_editable_by(user)
            # Completed lesson IDs
            profile = getattr(user, 'profile', None)
            completed_lesson_ids = set(
                LessonProgress.objects.filter(
                    user=profile,
                    lesson__chapter__course=course,
                    is_completed=True,
                ).values_list('lesson_id', flat=True)
            ) if profile else set()
            context['completed_lesson_ids'] = completed_lesson_ids
            # Certificate if completed
            context['certificate'] = Certificate.objects.filter(user=profile, course=course).first() if profile else None
        else:
            context['enrollment'] = None
            context['is_instructor'] = False
            context['completed_lesson_ids'] = set()
            context['certificate'] = None

        return context


class CourseEnrollView(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_accessible_by(request.user):
            raise PermissionDenied()

        # Check self-enrollment permission
        if not course.allow_self_enrollment and not course.is_editable_by(request.user):
            messages.error(request, _('Khóa học này không cho phép tự đăng ký. Vui lòng liên hệ Giảng viên để được thêm thủ công.'))
            return redirect('course_detail', slug=course.key)

        defaults = {'status': Enrollment.STATUS_ACTIVE, 'progress_percentage': 0.0}
        if course.validity_duration_days:
            defaults['expiry_date'] = timezone.now() + timedelta(days=course.validity_duration_days)

        enrollment, created = Enrollment.objects.get_or_create(
            user=request.profile,
            course=course,
            defaults=defaults,
        )
        if created:
            enrollment.recalculate_progress()
        elif enrollment.is_expired:
            if course.validity_duration_days:
                enrollment.expiry_date = timezone.now() + timedelta(days=course.validity_duration_days)
            else:
                enrollment.expiry_date = None
            enrollment.status = Enrollment.STATUS_ACTIVE
            enrollment.save(update_fields=['expiry_date', 'status'])

        # Find first lesson or go to detail
        first_chapter = course.chapters.first()
        if first_chapter:
            first_lesson = first_chapter.lessons.filter(is_published=True).first()
            if first_lesson:
                return redirect('course_lesson', slug=course.key, lesson_id=first_lesson.id)

        return redirect('course_detail', slug=course.key)


class LessonLearnView(LoginRequiredMixin, TitleMixin, TemplateView):
    template_name = 'course/lesson_learn.html'

    def get_title(self):
        return f'{self.lesson.title} | {self.course.title} - LMS HNUEOJ'

    def dispatch(self, request, slug, lesson_id, *args, **kwargs):
        self.course = get_object_or_404(Course, key=slug)
        if not self.course.is_accessible_by(request.user):
            raise Http404()

        is_teacher = self.course.is_editable_by(request.user)
        self.enrollment = self.course.get_enrollment(request.user)

        # Non-teacher users MUST be enrolled to access lessons
        if not is_teacher and not self.enrollment:
            from django.contrib import messages
            messages.warning(request, _('Bạn cần ghi danh học phần trước khi bắt đầu học tập và làm bài.'))
            return redirect('course_detail', slug=self.course.key)

        self.lesson = get_object_or_404(
            Lesson.objects.select_related('chapter__course'),
            id=lesson_id,
            chapter__course=self.course,
        )

        if not is_teacher and not self.lesson.is_accessible_by(request.user):
            from django.contrib import messages
            messages.warning(request, _('Bài giảng này hiện đang tạm khóa hoặc chưa được xuất bản bởi Giảng viên.'))
            return redirect('course_detail', slug=self.course.key)

        return super().dispatch(request, slug, lesson_id, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.course
        user = self.request.user

        chapters = course.chapters.prefetch_related('lessons', 'exams').all()
        context['course'] = course
        context['current_lesson'] = self.lesson
        context['chapters'] = chapters
        context['enrollment'] = self.enrollment

        # Progress of current lesson
        progress = LessonProgress.objects.filter(user=user.profile, lesson=self.lesson).first()
        context['is_completed'] = progress.is_completed if progress else False

        # Practice problems & student scores
        lesson_problems = list(self.lesson.lesson_problems.select_related('problem').all())
        problem_scores = {}
        completed_required_count = 0
        total_required_count = 0

        for lp in lesson_problems:
            if lp.is_required_for_completion:
                total_required_count += 1

            best_sub = Submission.objects.filter(
                user=user.profile,
                problem=lp.problem,
            ).order_by('-points', '-date').first()

            is_ac = best_sub and best_sub.result == 'AC'
            if lp.is_required_for_completion and is_ac:
                completed_required_count += 1

            problem_scores[lp.id] = {
                'points': best_sub.points if best_sub else 0,
                'result': best_sub.result if best_sub else None,
                'is_ac': is_ac,
                'best_submission_id': best_sub.id if best_sub else None,
            }

        context['lesson_problems'] = lesson_problems
        context['problem_scores'] = problem_scores
        context['total_required_count'] = total_required_count
        context['completed_required_count'] = completed_required_count
        context['can_complete_lesson'] = (total_required_count == 0 or completed_required_count == total_required_count)
        context['has_required_problems'] = total_required_count > 0
        context['available_languages'] = Language.objects.all()

        # Completed lesson IDs
        context['completed_lesson_ids'] = set(
            LessonProgress.objects.filter(
                user=user.profile,
                lesson__chapter__course=course,
                is_completed=True,
            ).values_list('lesson_id', flat=True)
        )

        # Prev / Next navigation
        all_lessons = list(Lesson.objects.filter(chapter__course=course, is_published=True).order_by('chapter__order_index', 'order_index', 'id'))
        current_idx = -1
        for i, l in enumerate(all_lessons):
            if l.id == self.lesson.id:
                current_idx = i
                break

        context['prev_lesson'] = all_lessons[current_idx - 1] if current_idx > 0 else None
        context['next_lesson'] = all_lessons[current_idx + 1] if 0 <= current_idx < len(all_lessons) - 1 else None

        return context


class ToggleLessonProgressAjax(LoginRequiredMixin, View):
    def post(self, request, slug, lesson_id):
        course = get_object_or_404(Course, key=slug)
        lesson = get_object_or_404(Lesson, id=lesson_id, chapter__course=course)

        enrollment = get_object_or_404(Enrollment, user=request.profile, course=course)

        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        is_completed = data.get('completed', None)

        progress = LessonProgress.objects.filter(user=request.profile, lesson=lesson).first()

        target_completed = (not progress.is_completed) if (progress and is_completed is None) else (bool(is_completed) if is_completed is not None else True)

        if target_completed:
            if not lesson.can_be_marked_completed_by(request.user):
                return JsonResponse({
                    'error': _('Bạn cần giải đúng (AC) tất cả các bài tập thực hành bắt buộc trước khi hoàn thành bài học.'),
                    'can_complete': False,
                }, status=400)

        progress, created = LessonProgress.objects.update_or_create(
            user=request.profile,
            lesson=lesson,
            defaults={'is_completed': target_completed, 'completed_at': timezone.now() if target_completed else None},
        )

        # Recalculate course enrollment progress
        new_percentage = enrollment.recalculate_progress()

        # Broadcast WebSocket event to instructor live monitor
        try:
            event.post('course_monitor_%d' % course.id, {
                'type': 'lesson_completed',
                'course_id': course.id,
                'user_id': request.profile.id,
                'username': request.user.username,
                'full_name': getattr(request.profile, 'display_name', '') or request.user.get_full_name() or request.user.username,
                'lesson_id': lesson.id,
                'lesson_title': lesson.title,
                'is_completed': progress.is_completed,
                'progress': new_percentage,
                'status': enrollment.status,
                'timestamp': timezone.now().isoformat(),
            })
        except Exception:
            pass

        return JsonResponse({
            'success': True,
            'is_completed': progress.is_completed,
            'progress_percentage': new_percentage,
            'enrollment_status': enrollment.status,
        })


class LessonSubmitAjax(LoginRequiredMixin, View):
    def post(self, request, slug, lesson_id):
        course = get_object_or_404(Course, key=slug)
        if not course.is_accessible_by(request.user):
            raise PermissionDenied()

        lesson = get_object_or_404(Lesson, id=lesson_id, chapter__course=course)

        problem_code = request.POST.get('problem_code')
        problem = get_object_or_404(Problem, code=problem_code)

        # Check problem is attached to lesson
        lp = get_object_or_404(LessonProblem, lesson=lesson, problem=problem)

        language_key = request.POST.get('language')
        language = get_object_or_404(Language, key=language_key)
        source_code = request.POST.get('source', '').strip()

        if not source_code:
            return JsonResponse({'error': _('Mã nguồn không được để trống.')}, status=400)

        with transaction.atomic():
            submission = Submission.objects.create(
                user=request.profile,
                problem=problem,
                language=language,
                lesson=lesson,
                status='QU',
            )
            SubmissionSource.objects.create(
                submission=submission,
                source=source_code,
            )

        judge_submission(submission)

        return JsonResponse({
            'success': True,
            'submission_id': submission.id,
            'status_url': reverse('submission_status', args=[submission.id]),
        })


class CourseManageView(LoginRequiredMixin, TitleMixin, TemplateView):
    template_name = 'course/course_manage.html'

    def get_title(self):
        return f'Quản trị Học liệu: {self.course.title} - LMS HNUEOJ'

    def dispatch(self, request, slug, *args, **kwargs):
        self.course = get_object_or_404(Course, key=slug)
        if not self.course.is_editable_by(request.user):
            raise PermissionDenied()
        return super().dispatch(request, slug, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course'] = self.course
        context['chapters'] = self.course.chapters.prefetch_related(
            'lessons__lesson_problems__problem',
            'chapter_contests__contest',
            'exams__exam_problems__problem'
        ).all()
        context['course_contests'] = self.course.course_contests.filter(scope_type=CourseContest.SCOPE_COURSE).select_related('contest')
        context['course_exams'] = self.course.exams.filter(target_type=Exam.TARGET_COURSE).prefetch_related('exam_problems__problem')
        context['available_languages'] = Language.objects.all()
        return context


class SaveCourseInfoAjax(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        price = data.get('price', 0)
        try:
            price = max(0, int(price))
        except (ValueError, TypeError):
            price = 0

        thumbnail_url = data.get('thumbnail_url', '').strip()
        status = data.get('status', course.status)
        is_public = bool(data.get('is_public', course.is_public))
        is_locked = bool(data.get('is_locked', course.is_locked))
        allow_self_enrollment = bool(data.get('allow_self_enrollment', course.allow_self_enrollment))

        validity_duration_days = data.get('validity_duration_days')
        if validity_duration_days is not None and str(validity_duration_days).strip() != '':
            try:
                validity_duration_days = max(1, int(validity_duration_days))
            except (ValueError, TypeError):
                validity_duration_days = None
        else:
            validity_duration_days = None

        reg_status = data.get('reg_status', course.reg_status)
        target_audience = data.get('target_audience', course.target_audience).strip()
        schedule_info = data.get('schedule_info', course.schedule_info).strip()
        format_type = data.get('format_type', course.format_type).strip()
        duration_info = data.get('duration_info', course.duration_info).strip()
        start_date_info = data.get('start_date_info', course.start_date_info).strip()
        contact_url = data.get('contact_url', course.contact_url).strip()

        if not title:
            return JsonResponse({'error': _('Tên khóa học không được để trống.')}, status=400)

        course.title = title
        course.description = description
        course.price = price
        course.thumbnail_url = thumbnail_url
        if status in dict(Course.STATUS_CHOICES):
            course.status = status
        if reg_status in dict(Course.REG_STATUS_CHOICES):
            course.reg_status = reg_status
        course.target_audience = target_audience
        course.schedule_info = schedule_info
        course.format_type = format_type
        course.duration_info = duration_info
        course.start_date_info = start_date_info
        course.contact_url = contact_url
        course.is_public = is_public
        course.is_locked = is_locked
        course.allow_self_enrollment = allow_self_enrollment
        course.validity_duration_days = validity_duration_days
        course.save()

        return JsonResponse({
            'success': True,
            'course': {
                'id': course.id,
                'key': course.key,
                'title': course.title,
                'price': course.price,
                'formatted_price': str(course.formatted_price),
                'status': course.status,
                'is_locked': course.is_locked,
                'is_public': course.is_public,
                'allow_self_enrollment': course.allow_self_enrollment,
                'validity_duration_days': course.validity_duration_days,
                'thumbnail_url': course.thumbnail_url,
            }
        })


class ToggleCourseItemLockAjax(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        item_type = data.get('item_type')
        item_id = data.get('item_id')

        if item_type == 'course':
            course.is_locked = not course.is_locked
            course.save(update_fields=['is_locked'])
            return JsonResponse({'success': True, 'is_locked': course.is_locked, 'item_type': 'course'})
        elif item_type == 'lesson':
            lesson = get_object_or_404(Lesson, id=item_id, chapter__course=course)
            lesson.is_locked = not lesson.is_locked
            lesson.save(update_fields=['is_locked'])
            return JsonResponse({'success': True, 'is_locked': lesson.is_locked, 'item_type': 'lesson', 'item_id': lesson.id})
        elif item_type == 'exam':
            exam = get_object_or_404(Exam, id=item_id, course=course)
            exam.is_locked = not exam.is_locked
            exam.save(update_fields=['is_locked'])
            return JsonResponse({'success': True, 'is_locked': exam.is_locked, 'item_type': 'exam', 'item_id': exam.id})

        return JsonResponse({'error': _('Loại đối tượng không hợp lệ.')}, status=400)


class SaveChapterAjax(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        chapter_id = data.get('id')
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        order_index = int(data.get('order_index', 0))

        if not title:
            return JsonResponse({'error': 'Tiêu đề chương không được để trống.'}, status=400)

        if chapter_id:
            chapter = get_object_or_404(Chapter, id=chapter_id, course=course)
            chapter.title = title
            chapter.description = description
            chapter.order_index = order_index
            chapter.save()
        else:
            chapter = Chapter.objects.create(
                course=course,
                title=title,
                description=description,
                order_index=order_index,
            )

        return JsonResponse({
            'success': True,
            'chapter': {
                'id': chapter.id,
                'title': chapter.title,
                'description': chapter.description,
                'order_index': chapter.order_index,
            },
        })


class SaveLessonAjax(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        lesson_id = data.get('id')
        chapter_id = data.get('chapter_id')
        title = data.get('title', '').strip()
        content = data.get('content', '')
        video_url = data.get('video_url', '').strip() or None
        estimated_minutes = int(data.get('estimated_minutes', 15))
        order_index = int(data.get('order_index', 0))
        is_published = data.get('is_published', True)
        is_locked = bool(data.get('is_locked', False))

        if not title:
            return JsonResponse({'error': 'Tiêu đề bài học không được để trống.'}, status=400)

        chapter = get_object_or_404(Chapter, id=chapter_id, course=course)

        if lesson_id:
            lesson = get_object_or_404(Lesson, id=lesson_id, chapter__course=course)
            lesson.chapter = chapter
            lesson.title = title
            lesson.content = content
            lesson.video_url = video_url
            lesson.estimated_minutes = estimated_minutes
            lesson.order_index = order_index
            lesson.is_published = is_published
            lesson.is_locked = is_locked
            lesson.save()
        else:
            lesson = Lesson.objects.create(
                chapter=chapter,
                title=title,
                content=content,
                video_url=video_url,
                estimated_minutes=estimated_minutes,
                order_index=order_index,
                is_published=is_published,
                is_locked=is_locked,
            )

        return JsonResponse({
            'success': True,
            'lesson': {
                'id': lesson.id,
                'title': lesson.title,
                'estimated_minutes': lesson.estimated_minutes,
                'order_index': lesson.order_index,
                'is_locked': lesson.is_locked,
            },
        })


class SaveLessonProblemAjax(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        lp_id = data.get('id')
        lesson_id = data.get('lesson_id')
        problem_code = data.get('problem_code', '').strip()
        alias = data.get('alias', '').strip()
        custom_score = data.get('custom_score')
        custom_score = float(custom_score) if custom_score not in (None, '') else None
        is_required = bool(data.get('is_required_for_completion', False))
        order_index = int(data.get('order_index', 0))

        lesson = get_object_or_404(Lesson, id=lesson_id, chapter__course=course)
        problem = get_object_or_404(Problem, code=problem_code)

        if lp_id:
            lp = get_object_or_404(LessonProblem, id=lp_id, lesson=lesson)
            lp.problem = problem
            lp.alias = alias
            lp.custom_score = custom_score
            lp.is_required_for_completion = is_required
            lp.order_index = order_index
            lp.save()
        else:
            lp, _ = LessonProblem.objects.update_or_create(
                lesson=lesson,
                problem=problem,
                defaults={
                    'alias': alias,
                    'custom_score': custom_score,
                    'is_required_for_completion': is_required,
                    'order_index': order_index,
                }
            )

        return JsonResponse({
            'success': True,
            'problem': {
                'id': lp.id,
                'code': problem.code,
                'name': lp.display_title,
                'points': lp.display_points,
                'is_required_for_completion': lp.is_required_for_completion,
                'order_index': lp.order_index,
            },
        })


class BatchSaveLessonProblemsAjax(LoginRequiredMixin, View):
    def post(self, request, slug, lesson_id):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        lesson = get_object_or_404(Lesson, id=lesson_id, chapter__course=course)
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        problems_data = data.get('problems', [])

        existing_lps = {lp.problem.code: lp for lp in lesson.lesson_problems.select_related('problem')}
        keep_codes = set()

        for idx, item in enumerate(problems_data):
            code = (item.get('problem_code') or '').strip()
            if not code:
                continue
            is_req = bool(item.get('is_required', False))
            order_idx = int(item.get('order', idx + 1))
            problem = Problem.objects.filter(code=code).first()
            if not problem:
                return JsonResponse({'error': _('Không tìm thấy bài tập với mã "%s"') % code}, status=400)

            if code in existing_lps:
                lp = existing_lps[code]
                lp.is_required_for_completion = is_req
                lp.order_index = order_idx
                lp.alias = ''
                lp.custom_score = None
                lp.save()
            else:
                LessonProblem.objects.create(
                    lesson=lesson,
                    problem=problem,
                    alias='',
                    custom_score=None,
                    is_required_for_completion=is_req,
                    order_index=order_idx,
                )
            keep_codes.add(code)

        # Remove deleted problems
        LessonProblem.objects.filter(lesson=lesson).exclude(problem__code__in=keep_codes).delete()

        return JsonResponse({'success': True})


class SaveExamAjax(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        exam_id = data.get('id')
        chapter_id = data.get('chapter_id')
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        exam_type = data.get('exam_type', Exam.TYPE_PRACTICE)
        pass_percentage = float(data.get('pass_percentage', 60.0))
        is_published = bool(data.get('is_published', True))
        is_locked = bool(data.get('is_locked', False))
        order_index = int(data.get('order_index', 0))

        if not title:
            return JsonResponse({'error': 'Tiêu đề kỳ thi không được để trống.'}, status=400)

        chapter = None
        if chapter_id:
            chapter = get_object_or_404(Chapter, id=chapter_id, course=course)

        target_type = Exam.TARGET_CHAPTER if chapter else Exam.TARGET_COURSE

        if exam_id:
            exam = get_object_or_404(Exam, id=exam_id, course=course)
            exam.chapter = chapter
            exam.target_type = target_type
            exam.title = title
            exam.description = description
            exam.exam_type = exam_type
            exam.pass_percentage = pass_percentage
            exam.is_published = is_published
            exam.is_locked = is_locked
            exam.order_index = order_index
            exam.save()
        else:
            exam = Exam.objects.create(
                course=course,
                chapter=chapter,
                target_type=target_type,
                title=title,
                description=description,
                exam_type=exam_type,
                pass_percentage=pass_percentage,
                is_published=is_published,
                is_locked=is_locked,
                order_index=order_index,
            )

        return JsonResponse({
            'success': True,
            'exam': {
                'id': exam.id,
                'title': exam.title,
                'description': exam.description,
                'exam_type': exam.exam_type,
                'pass_percentage': exam.pass_percentage,
                'is_published': exam.is_published,
                'is_locked': exam.is_locked,
                'order_index': exam.order_index,
            },
        })


class SaveExamProblemAjax(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        ep_id = data.get('id')
        exam_id = data.get('exam_id')
        problem_code = data.get('problem_code', '').strip()
        alias = data.get('alias', '').strip()
        custom_score = data.get('custom_score')
        custom_score = float(custom_score) if custom_score not in (None, '') else None
        order_index = int(data.get('order_index', 0))

        exam = get_object_or_404(Exam, id=exam_id, course=course)
        problem = get_object_or_404(Problem, code=problem_code)

        if ep_id:
            ep = get_object_or_404(ExamProblem, id=ep_id, exam=exam)
            ep.problem = problem
            ep.alias = alias
            ep.custom_score = custom_score
            ep.order_index = order_index
            ep.save()
        else:
            ep, _ = ExamProblem.objects.update_or_create(
                exam=exam,
                problem=problem,
                defaults={
                    'alias': alias,
                    'custom_score': custom_score,
                    'order_index': order_index,
                }
            )

        return JsonResponse({
            'success': True,
            'problem': {
                'id': ep.id,
                'code': problem.code,
                'name': ep.display_title,
                'points': ep.display_points,
                'order_index': ep.order_index,
            },
        })


class BatchSaveExamProblemsAjax(LoginRequiredMixin, View):
    def post(self, request, slug, exam_id):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        exam = get_object_or_404(Exam, id=exam_id, course=course)
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        problems_data = data.get('problems', [])

        existing_eps = {ep.problem.code: ep for ep in exam.exam_problems.select_related('problem')}
        keep_codes = set()

        for idx, item in enumerate(problems_data):
            code = (item.get('problem_code') or '').strip()
            if not code:
                continue
            order_idx = int(item.get('order', idx + 1))
            custom_score = item.get('custom_score')
            custom_score = float(custom_score) if custom_score not in (None, '') else None

            problem = Problem.objects.filter(code=code).first()
            if not problem:
                return JsonResponse({'error': _('Không tìm thấy bài tập với mã "%s"') % code}, status=400)

            if code in existing_eps:
                ep = existing_eps[code]
                ep.order_index = order_idx
                if custom_score is not None:
                    ep.custom_score = custom_score
                ep.save()
            else:
                ExamProblem.objects.create(
                    exam=exam,
                    problem=problem,
                    order_index=order_idx,
                    custom_score=custom_score,
                )
            keep_codes.add(code)

        for code, ep in existing_eps.items():
            if code not in keep_codes:
                ep.delete()

        return JsonResponse({'success': True})


class ExamDetailView(LoginRequiredMixin, TitleMixin, TemplateView):
    template_name = 'course/exam_detail.html'

    def get_title(self):
        return f'{self.exam.title} - LMS HNUEOJ'

    def dispatch(self, request, slug, exam_id, *args, **kwargs):
        self.course = get_object_or_404(Course, key=slug)
        self.exam = get_object_or_404(Exam, id=exam_id, course=self.course)
        if not self.exam.can_access(request.user) and not self.course.is_editable_by(request.user):
            raise PermissionDenied()
        return super().dispatch(request, slug, exam_id, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course'] = self.course
        context['exam'] = self.exam
        context['exam_problems'] = self.exam.exam_problems.select_related('problem').all()
        return context


class ExamSubmitView(LoginRequiredMixin, View):
    def get(self, request, slug, exam_id):
        return HttpResponseRedirect(reverse('course_exam', args=[slug, exam_id]))

    def post(self, request, slug, exam_id):
        course = get_object_or_404(Course, key=slug)
        exam = get_object_or_404(Exam, id=exam_id, course=course)
        if not exam.can_access(request.user) and not course.is_editable_by(request.user):
            raise PermissionDenied()

        problem_code = request.POST.get('problem_code')
        problem = get_object_or_404(Problem, code=problem_code)
        ep = get_object_or_404(ExamProblem, exam=exam, problem=problem)

        language_key = request.POST.get('language')
        language = get_object_or_404(Language, key=language_key)
        source_code = request.POST.get('source', '').strip()

        if not source_code:
            return JsonResponse({'error': _('Mã nguồn không được để trống.')}, status=400)

        with transaction.atomic():
            submission = Submission.objects.create(
                user=request.profile,
                problem=problem,
                language=language,
                exam=exam,
                status='QU',
            )
            SubmissionSource.objects.create(
                submission=submission,
                source=source_code,
            )

        judge_submission(submission)

        return JsonResponse({
            'success': True,
            'submission_id': submission.id,
        })




class CourseProblemSearchAjax(LoginRequiredMixin, View):
    def get(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        q = request.GET.get('q', '').strip()
        qs = Problem.get_visible_problems(request.user)
        if q:
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))

        results = []
        for prob in qs.order_by('code')[:40]:
            results.append({
                'id': prob.id,
                'code': prob.code,
                'name': prob.name,
                'points': prob.points or 100,
            })

        return JsonResponse({'results': results})


class DeleteCourseItemAjax(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        item_type = data.get('item_type')
        item_id = data.get('item_id')

        if item_type == 'chapter':
            Chapter.objects.filter(id=item_id, course=course).delete()
        elif item_type == 'lesson':
            Lesson.objects.filter(id=item_id, chapter__course=course).delete()
        elif item_type == 'lesson_problem':
            LessonProblem.objects.filter(id=item_id, lesson__chapter__course=course).delete()
        elif item_type == 'course_contest':
            cc = CourseContest.objects.filter(id=item_id, course=course).first()
            if cc:
                contest = cc.contest
                cc.delete()
                if contest and contest.is_course_only and not contest.course_mappings.exists():
                    contest.delete()
        elif item_type == 'exam':
            Exam.objects.filter(id=item_id, course=course).delete()
        elif item_type == 'exam_problem':
            ExamProblem.objects.filter(id=item_id, exam__course=course).delete()

        return JsonResponse({'success': True})


class CourseMonitorView(LoginRequiredMixin, TitleMixin, TemplateView):
    template_name = 'course/course_monitor.html'

    def get_title(self):
        return f'Live Proctoring: {self.course.title} - LMS HNUEOJ'

    def dispatch(self, request, slug, *args, **kwargs):
        self.course = get_object_or_404(Course, key=slug)
        if not self.course.is_editable_by(request.user):
            raise PermissionDenied()
        return super().dispatch(request, slug, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.course
        context['course'] = course

        # Stats
        enrollments = Enrollment.objects.filter(course=course).select_related('user__user')
        context['total_students'] = enrollments.count()
        context['ready_for_review_count'] = enrollments.filter(status=Enrollment.STATUS_READY_FOR_REVIEW).count()
        context['completed_count'] = enrollments.filter(status=Enrollment.STATUS_COMPLETED).count()

        context['enrollments'] = enrollments.order_by('-last_accessed_at')
        return context


class CourseMonitorDataAjax(LoginRequiredMixin, View):
    def get(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        enrollments = Enrollment.objects.filter(course=course).select_related('user__user')
        students_data = []
        for e in enrollments:
            cert = Certificate.objects.filter(user=e.user, course=course).first()
            status_display = Enrollment.STATUS_EXPIRED if e.is_expired else e.status
            students_data.append({
                'enrollment_id': e.id,
                'user_id': e.user.id,
                'username': e.user.user.username,
                'full_name': getattr(e.user, 'display_name', '') or e.user.user.get_full_name() or e.user.user.username,
                'progress': e.progress_percentage,
                'status': status_display,
                'is_expired': e.is_expired,
                'enrolled_at': e.enrolled_at.strftime('%d/%m/%Y %H:%M'),
                'expiry_date': e.expiry_date.strftime('%d/%m/%Y %H:%M') if e.expiry_date else _('Vô thời hạn'),
                'last_active': e.last_accessed_at.strftime('%d/%m/%Y %H:%M'),
                'has_certificate': bool(cert),
                'cert_code': cert.cert_code if cert else None,
            })

        recent_subs = Submission.objects.filter(
            Q(exam__course=course) | Q(lesson__chapter__course=course)
        ).select_related('user__user', 'problem', 'language', 'exam', 'lesson').order_by('-date')[:25]

        submissions_data = []
        for s in recent_subs:
            submissions_data.append({
                'id': s.id,
                'username': s.user.user.username,
                'full_name': getattr(s.user, 'display_name', '') or s.user.user.get_full_name() or s.user.user.username,
                'problem_code': s.problem.code,
                'problem_name': s.problem.name,
                'exam_title': s.exam.title if s.exam else (s.lesson.title if s.lesson else ''),
                'language': str(s.language),
                'status': s.status,
                'result': s.result,
                'points': s.points,
                'time': s.time,
                'memory': s.memory,
                'date': s.date.strftime('%H:%M:%S %d/%m'),
            })

        return JsonResponse({
            'students': students_data,
            'recent_submissions': submissions_data,
        })


class SubmissionGodModeAjax(LoginRequiredMixin, View):
    def get(self, request, slug, submission_id):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        submission = get_object_or_404(
            Submission.objects.select_related('user__user', 'problem', 'language', 'exam', 'lesson', 'source'),
            Q(exam__course=course) | Q(lesson__chapter__course=course),
            id=submission_id,
        )

        test_cases = []
        for tc in submission.test_cases.order_by('case'):
            test_cases.append({
                'case': tc.case,
                'status': tc.status,
                'time': tc.time,
                'memory': tc.memory,
                'points': tc.points,
                'total': tc.total,
                'feedback': tc.feedback,
            })

        source_code = submission.source.source if hasattr(submission, 'source') and submission.source else ''

        return JsonResponse({
            'submission': {
                'id': submission.id,
                'username': submission.user.user.username,
                'full_name': getattr(submission.user, 'display_name', '') or submission.user.user.get_full_name() or submission.user.user.username,
                'problem_code': submission.problem.code,
                'problem_name': submission.problem.name,
                'language': str(submission.language),
                'result': submission.result,
                'points': submission.points,
                'time': submission.time,
                'memory': submission.memory,
                'error': submission.error or '',
                'date': submission.date.strftime('%d/%m/%Y %H:%M:%S'),
                'source': source_code,
                'test_cases': test_cases,
            },
        })


class IssueCertificateAjax(LoginRequiredMixin, View):
    def post(self, request, slug, enrollment_id):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        enrollment = get_object_or_404(Enrollment, id=enrollment_id, course=course)

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        grade = data.get('grade', 'Xuất sắc')

        with transaction.atomic():
            cert_code = Certificate.generate_cert_code(course.id, enrollment.user_id)
            cert, created = Certificate.objects.update_or_create(
                user=enrollment.user,
                course=course,
                defaults={
                    'cert_code': cert_code,
                    'issued_by': request.profile,
                    'issued_date': timezone.now(),
                    'grade': grade,
                    'verification_url': request.build_absolute_uri(reverse('certificate_detail', args=[cert_code])),
                },
            )
            enrollment.status = Enrollment.STATUS_COMPLETED
            enrollment.completed_at = timezone.now()
            enrollment.save(update_fields=['status', 'completed_at'])

        return JsonResponse({
            'success': True,
            'cert_code': cert.cert_code,
            'verification_url': cert.verification_url,
        })


class RevokeCertificateAjax(LoginRequiredMixin, View):
    def post(self, request, slug, enrollment_id):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        enrollment = get_object_or_404(Enrollment, id=enrollment_id, course=course)
        Certificate.objects.filter(user=enrollment.user, course=course).delete()

        if enrollment.status == Enrollment.STATUS_COMPLETED:
            enrollment.status = Enrollment.STATUS_ACTIVE
            enrollment.save(update_fields=['status'])

        return JsonResponse({'success': True})


class CertificateDetailView(TitleMixin, DetailView):
    model = Certificate
    slug_field = 'cert_code'
    slug_url_kwarg = 'cert_code'
    template_name = 'course/certificate_detail.html'
    context_object_name = 'certificate'

    def get_title(self):
        return f'Chứng nhận Hoàn thành: {self.object.user.user.username} | {self.object.course.title} - LMS HNUEOJ'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verification_url'] = self.request.build_absolute_uri(self.object.get_absolute_url())
        return context


class CertificatePdfView(DetailView):
    model = Certificate
    slug_field = 'cert_code'
    slug_url_kwarg = 'cert_code'
    template_name = 'course/certificate_pdf.html'
    context_object_name = 'certificate'


class CourseAddStudentsAjax(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        raw_input = data.get('users', '').strip()
        custom_days = data.get('days')

        if not raw_input:
            return JsonResponse({'error': _('Vui lòng nhập tên đăng nhập, email hoặc họ tên học viên.')}, status=400)

        raw_tokens = [t.strip() for t in re.split(r'[\s,\n;]+', raw_input) if t.strip()]
        if not raw_tokens:
            return JsonResponse({'error': _('Danh sách học viên không hợp lệ.')}, status=400)

        days_to_add = None
        if custom_days is not None and str(custom_days).isdigit() and int(custom_days) > 0:
            days_to_add = int(custom_days)
        elif course.validity_duration_days:
            days_to_add = course.validity_duration_days

        q_filter = Q()
        for token in raw_tokens:
            q_filter |= Q(user__username__iexact=token)
            q_filter |= Q(user__email__iexact=token)
            q_filter |= Q(username_display_override__iexact=token)
            q_filter |= Q(user__first_name__iexact=token)
            q_filter |= Q(user__last_name__iexact=token)

        matched_profiles = list(Profile.objects.filter(q_filter).select_related('user'))

        found_identifiers = set()
        added_count = 0
        renewed_count = 0

        now = timezone.now()
        for profile in matched_profiles:
            found_identifiers.add(profile.user.username.lower())
            if profile.user.email:
                found_identifiers.add(profile.user.email.lower())
            if profile.username_display_override:
                found_identifiers.add(profile.username_display_override.lower())
            if profile.user.first_name:
                found_identifiers.add(profile.user.first_name.lower())
            if profile.user.last_name:
                found_identifiers.add(profile.user.last_name.lower())
            
            expiry_dt = now + timedelta(days=days_to_add) if days_to_add else None
            enrollment, created = Enrollment.objects.get_or_create(
                user=profile,
                course=course,
                defaults={'status': Enrollment.STATUS_ACTIVE, 'progress_percentage': 0.0, 'expiry_date': expiry_dt},
            )
            if created:
                enrollment.recalculate_progress()
                added_count += 1
            else:
                enrollment.expiry_date = expiry_dt
                if enrollment.status == Enrollment.STATUS_EXPIRED:
                    enrollment.status = Enrollment.STATUS_ACTIVE
                enrollment.save(update_fields=['expiry_date', 'status'])
                renewed_count += 1

        unfound = [t for t in raw_tokens if t.lower() not in found_identifiers]

        msg = f'Đã thêm {added_count} học viên mới và gia hạn/cập nhật cho {renewed_count} học viên.'
        return JsonResponse({
            'success': True,
            'added_count': added_count,
            'renewed_count': renewed_count,
            'unfound_users': unfound,
            'message': msg
        })


class CourseRemoveStudentAjax(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        enrollment_id = data.get('enrollment_id')
        user_identifier = data.get('user', '').strip()

        if enrollment_id:
            enrollment = get_object_or_404(Enrollment, id=enrollment_id, course=course)
            username = enrollment.user.user.username
            enrollment.delete()
            return JsonResponse({'success': True, 'message': _(f'Đã xóa học viên @{username} khỏi khóa học.')})
        elif user_identifier:
            profile = Profile.objects.filter(
                Q(user__username__iexact=user_identifier) | Q(user__email__iexact=user_identifier)
            ).first()
            if not profile:
                return JsonResponse({'error': _('Không tìm thấy học viên.')}, status=404)
            deleted_count, _details = Enrollment.objects.filter(user=profile, course=course).delete()
            if deleted_count == 0:
                return JsonResponse({'error': _('Học viên này chưa ghi danh khóa học.')}, status=400)
            return JsonResponse({'success': True, 'message': _(f'Đã xóa học viên @{profile.user.username} khỏi khóa học.')})

        return JsonResponse({'error': _('Vui lòng chỉ định học viên cần xóa.')}, status=400)


class CourseRenewEnrollmentAjax(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        enrollment_id = data.get('enrollment_id')
        enrollment_ids = data.get('enrollment_ids', [])
        if enrollment_id:
            enrollment_ids.append(enrollment_id)

        days = data.get('days')
        target_date_str = data.get('target_date')

        if not enrollment_ids:
            return JsonResponse({'error': _('Vui lòng chọn học viên cần gia hạn.')}, status=400)

        enrollments = Enrollment.objects.filter(id__in=enrollment_ids, course=course)
        now = timezone.now()
        updated_list = []

        for e in enrollments:
            if days and str(days).isdigit():
                add_days = int(days)
                base_time = e.expiry_date if (e.expiry_date and e.expiry_date > now) else now
                e.expiry_date = base_time + timedelta(days=add_days)
            elif target_date_str:
                try:
                    target_dt = datetime.strptime(target_date_str, '%Y-%m-%d')
                    e.expiry_date = timezone.make_aware(target_dt)
                except ValueError:
                    pass
            elif course.validity_duration_days:
                e.expiry_date = now + timedelta(days=course.validity_duration_days)

            if e.status == Enrollment.STATUS_EXPIRED:
                e.status = Enrollment.STATUS_ACTIVE

            e.save(update_fields=['expiry_date', 'status'])
            updated_list.append({
                'enrollment_id': e.id,
                'username': e.user.user.username,
                'expiry_date': e.expiry_date.strftime('%d/%m/%Y %H:%M') if e.expiry_date else _('Vô thời hạn'),
                'is_expired': e.is_expired,
            })

        return JsonResponse({
            'success': True,
            'updated_count': len(updated_list),
            'enrollments': updated_list,
        })


def build_exam_ranking_data(course, exam, request):
    _user_url_tpl = reverse('user_page', args=['__USERNAME__'])
    _org_url_tpl = reverse('organization_home', args=['__SLUG__'])

    exam_problems = list(exam.exam_problems.select_related('problem').order_by('order_index', 'id'))
    exam_prob_map = {ep.problem_id: ep for ep in exam_problems}

    problems_data = []
    for i, ep in enumerate(exam_problems):
        prob_pts = ep.display_points
        r_pts = round(float(prob_pts), 2)
        clean_pts = int(r_pts) if r_pts.is_integer() else r_pts
        problems_data.append({
            'id': ep.problem_id,
            'code': ep.problem.code,
            'label': chr(65 + i) if i < 26 else f'P{i+1}',
            'name': ep.display_title,
            'points': clean_pts,
            'url': reverse('problem_detail', args=[ep.problem.code]),
        })

    contest_data = {
        'key': f'exam_{exam.id}',
        'name': exam.title,
        'format': 'default',
        'format_config': {},
        'can_edit': course.is_editable_by(request.user),
        'points_precision': 2,
        'ended': not exam.is_active if (exam.start_time or exam.end_time) else False,
        'url_templates': {
            'all_submissions': reverse('course_exam', args=[course.key, exam.id]),
            'problem_submissions': reverse('course_exam', args=[course.key, exam.id]),
        },
        'rank_header': _('Hạng'),
    }

    enrollments = Enrollment.objects.filter(course=course).select_related('user__user').prefetch_related('user__organizations')
    profile_map = {e.user_id: e.user for e in enrollments}

    sub_user_ids = set(Submission.objects.filter(exam=exam).values_list('user_id', flat=True))
    missing_uids = sub_user_ids - set(profile_map.keys())
    if missing_uids:
        extra_profiles = Profile.objects.filter(id__in=missing_uids).select_related('user').prefetch_related('organizations')
        for p in extra_profiles:
            profile_map[p.id] = p

    submissions = Submission.objects.filter(
        exam=exam,
    ).select_related('user__user', 'problem').order_by('date')

    user_sub_data = {}
    for sub in submissions:
        uid = sub.user_id
        pid = sub.problem_id
        if pid not in exam_prob_map:
            continue

        if uid not in user_sub_data:
            user_sub_data[uid] = {}
        if pid not in user_sub_data[uid]:
            user_sub_data[uid][pid] = {'tries': 0, 'best_sub': None}

        user_sub_data[uid][pid]['tries'] += 1

        if sub.points is not None:
            cur_best = user_sub_data[uid][pid]['best_sub']
            if cur_best is None or sub.points > cur_best.points:
                user_sub_data[uid][pid]['best_sub'] = sub

    start_ref = exam.start_time or course.created_at

    participations_data = []
    for uid, profile in profile_map.items():
        user = profile.user
        org = profile.organization
        u_subs = user_sub_data.get(uid, {})

        format_data = {}
        total_score = 0.0
        total_cumtime = 0
        ac_count = 0

        for ep in exam_problems:
            pid = ep.problem_id
            p_str = str(pid)
            p_data = u_subs.get(pid)

            if not p_data or p_data['tries'] == 0:
                continue

            tries = p_data['tries']
            best_sub = p_data['best_sub']

            if best_sub and best_sub.points is not None:
                scaled_points = best_sub.points
                if ep.custom_score is not None and ep.problem.points:
                    scale = ep.custom_score / ep.problem.points
                    scaled_points = min(ep.custom_score, best_sub.points * scale)

                r_p = round(float(scaled_points), 2)
                clean_pts = int(r_p) if r_p.is_integer() else r_p

                time_sec = max(0, int((best_sub.date - start_ref).total_seconds()))

                format_data[p_str] = {
                    'points': clean_pts,
                    'time': time_sec,
                    'tries': tries,
                }
                total_score += clean_pts
                total_cumtime += time_sec
                if best_sub.result == 'AC' or clean_pts >= (ep.display_points or 100):
                    ac_count += 1
            else:
                format_data[p_str] = {
                    'points': 0,
                    'time': 0,
                    'tries': tries,
                }

        r_tot = round(float(total_score), 2)
        clean_tot = int(r_tot) if r_tot.is_integer() else r_tot

        user_dict = {
            'username': user.username,
            'display_name': getattr(profile, 'display_name', '') or user.get_full_name() or user.username,
            'name': user.get_full_name() or user.username,
            'css_class': Profile.get_user_css_class(profile.display_rank, profile.rating),
            'url': _user_url_tpl.replace('__USERNAME__', user.username),
            'organization': {
                'short_name': org.short_name or org.name,
                'url': _org_url_tpl.replace('__SLUG__', org.slug),
            } if org else None,
        }

        participations_data.append({
            'id': profile.id,
            'score': clean_tot,
            'cumtime': total_cumtime,
            'tiebreaker': 0,
            'is_disqualified': False,
            'virtual': 0,
            'user': user_dict,
            'format_data': format_data,
            'ac_count': ac_count,
        })

    participations_data.sort(key=lambda x: (-x['score'], -x['ac_count'], x['cumtime'], x['user']['username']))

    rank = 0
    delta = 1
    last_key = None
    for p in participations_data:
        key = (p['score'], p['cumtime'])
        if key != last_key:
            rank += delta
            delta = 0
        delta += 1
        p['rank'] = rank
        last_key = key
        del p['ac_count']

    return {
        'contest': contest_data,
        'problems': problems_data,
        'participations': participations_data,
    }




class CourseExamRankingView(LoginRequiredMixin, TitleMixin, TemplateView):
    template_name = 'course/exam_ranking.html'

    def get_title(self):
        return f'Bảng xếp hạng: {self.exam.title} - LMS HNUEOJ'

    def dispatch(self, request, slug, exam_id, *args, **kwargs):
        self.course = get_object_or_404(Course, key=slug)
        self.exam = get_object_or_404(Exam, id=exam_id, course=self.course)
        if not self.exam.can_access(request.user) and not self.course.is_editable_by(request.user):
            raise PermissionDenied()
        return super().dispatch(request, slug, exam_id, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if request.GET.get('data') is not None or request.headers.get('x-requested-with') == 'XMLHttpRequest':
            data = build_exam_ranking_data(self.course, self.exam, request)
            return JsonResponse(data)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = build_exam_ranking_data(self.course, self.exam, self.request)
        context['course'] = self.course
        context['exam'] = self.exam
        context['ranking_data'] = data
        context['ranking_json'] = json.dumps(data).translate(_json_script_escapes)
        context['contest_key'] = f'exam_{self.exam.id}'
        context['data_url'] = reverse('course_exam_ranking_data', args=[self.course.key, self.exam.id])
        return context


class CourseExamRankingDataAjax(LoginRequiredMixin, View):
    def get(self, request, slug, exam_id):
        course = get_object_or_404(Course, key=slug)
        exam = get_object_or_404(Exam, id=exam_id, course=course)

        if not exam.can_access(request.user) and not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = build_exam_ranking_data(course, exam, request)
        return JsonResponse(data)


class CourseContestDetailView(LoginRequiredMixin, View):
    def dispatch(self, request, slug, cc_id, *args, **kwargs):
        course = get_object_or_404(Course, key=slug)
        cc = get_object_or_404(CourseContest, id=cc_id, course=course)

        if not course.is_accessible_by(request.user):
            raise Http404(_('Khóa học không tồn tại hoặc bạn không có quyền truy cập.'))

        is_instructor = course.is_editable_by(request.user)

        if not cc.contest.is_visible and not is_instructor and not request.user.has_perm('judge.see_private_contest'):
            raise Http404(_('Kỳ thi chưa được mở công khai.'))

        profile = getattr(request.user, 'profile', None)
        if profile and (course.is_enrolled(request.user) or is_instructor):
            ContestParticipation.objects.get_or_create(
                contest=cc.contest,
                user=profile,
                defaults={'virtual': ContestParticipation.LIVE, 'real_start': timezone.now()}
            )

        return redirect('contest_view', contest=cc.contest.key)


class SaveCourseContestAjax(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        cc_id = data.get('id')
        contest_id = data.get('contest_id')
        chapter_id = data.get('chapter_id')
        scope_type = data.get('scope_type', CourseContest.SCOPE_CHAPTER)
        weight = float(data.get('weight', 1.0))
        passing_grade = float(data.get('passing_grade', 50.0))
        is_required = bool(data.get('is_required', True))
        order_index = int(data.get('order_index', 0))

        name = data.get('name')
        description = data.get('description')
        time_limit_mins = data.get('time_limit_mins')
        format_name = data.get('format_name')
        problems = data.get('problems')

        chapter = None
        if scope_type == CourseContest.SCOPE_CHAPTER and chapter_id:
            chapter = get_object_or_404(Chapter, id=chapter_id, course=course)

        if cc_id:
            cc = get_object_or_404(CourseContest, id=cc_id, course=course)
            cc.chapter = chapter
            cc.scope_type = scope_type
            cc.weight = weight
            cc.passing_grade = passing_grade
            cc.is_required = is_required
            cc.order_index = order_index
            cc.save()

            contest = cc.contest
            if name:
                contest.name = name.strip()
            if description is not None:
                contest.description = description.strip()
            if time_limit_mins is not None:
                contest.time_limit = timedelta(minutes=int(time_limit_mins)) if time_limit_mins else None
            if format_name:
                contest.format_name = format_name
            contest.save()

            if problems is not None:
                from judge.models import ContestProblem, Problem
                ContestProblem.objects.filter(contest=contest).delete()
                for idx, p_item in enumerate(problems, 1):
                    p_code = p_item.get('code', '').strip() if isinstance(p_item, dict) else str(p_item).strip()
                    p_pts = p_item.get('points', 100) if isinstance(p_item, dict) else 100
                    prob = Problem.objects.filter(code=p_code).first()
                    if prob:
                        ContestProblem.objects.create(
                            contest=contest,
                            problem=prob,
                            points=p_pts,
                            order=idx
                        )
        else:
            contest = get_object_or_404(Contest, id=contest_id)
            cc, created = CourseContest.objects.get_or_create(
                course=course,
                contest=contest,
                defaults={
                    'chapter': chapter,
                    'scope_type': scope_type,
                    'weight': weight,
                    'passing_grade': passing_grade,
                    'is_required': is_required,
                    'order_index': order_index,
                }
            )
            if not created:
                cc.chapter = chapter
                cc.scope_type = scope_type
                cc.weight = weight
                cc.passing_grade = passing_grade
                cc.is_required = is_required
                cc.order_index = order_index
                cc.save()

        return JsonResponse({
            'success': True,
            'course_contest': {
                'id': cc.id,
                'contest_id': cc.contest_id,
                'contest_name': cc.contest.name,
                'contest_key': cc.contest.key,
                'scope_type': cc.scope_type,
                'weight': cc.weight,
                'passing_grade': cc.passing_grade,
                'is_required': cc.is_required,
                'order_index': cc.order_index,
            }
        })


class CreateCourseContestAjax(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        name = data.get('name', '').strip()
        key = data.get('key', '').strip()
        description = data.get('description', '').strip()
        chapter_id = data.get('chapter_id')
        scope_type = data.get('scope_type', CourseContest.SCOPE_CHAPTER)
        time_limit_mins = data.get('time_limit_mins')
        format_name = data.get('format_name', 'atcoder')
        weight = float(data.get('weight', 1.0))
        passing_grade = float(data.get('passing_grade', 50.0))
        is_required = bool(data.get('is_required', True))
        problems = data.get('problems', [])

        if not name:
            return JsonResponse({'error': 'Tên Contest không được để trống.'}, status=400)

        if not key:
            key = f"c{course.id}-ct-{timezone.now().strftime('%Y%m%d%H%M%S')}"[:30]

        if Contest.objects.filter(key=key).exists():
            return JsonResponse({'error': f'Mã Contest "{key}" đã tồn tại trên hệ thống.'}, status=400)

        chapter = None
        if scope_type == CourseContest.SCOPE_CHAPTER and chapter_id:
            chapter = get_object_or_404(Chapter, id=chapter_id, course=course)

        now = timezone.now()
        start_time = now
        end_time = now + timedelta(days=365)
        time_limit = timedelta(minutes=int(time_limit_mins)) if time_limit_mins else None

        contest = Contest.objects.create(
            key=key,
            name=name,
            description=description,
            start_time=start_time,
            end_time=end_time,
            time_limit=time_limit,
            is_visible=False,
            is_course_only=True,
            is_course_private=True,
            course=course,
            format_name=format_name,
        )
        if hasattr(request.user, 'profile'):
            contest.authors.add(request.user.profile)

        if problems:
            from judge.models import ContestProblem, Problem
            for idx, p_item in enumerate(problems, 1):
                p_code = p_item.get('code', '').strip() if isinstance(p_item, dict) else str(p_item).strip()
                p_pts = p_item.get('points', 100) if isinstance(p_item, dict) else 100
                prob = Problem.objects.filter(code=p_code).first()
                if prob:
                    ContestProblem.objects.create(
                        contest=contest,
                        problem=prob,
                        points=p_pts,
                        order=idx
                    )

        cc = CourseContest.objects.create(
            course=course,
            chapter=chapter,
            contest=contest,
            scope_type=scope_type,
            weight=weight,
            passing_grade=passing_grade,
            is_required=is_required,
        )

        return JsonResponse({
            'success': True,
            'course_contest': {
                'id': cc.id,
                'contest_id': contest.id,
                'contest_name': contest.name,
                'contest_key': contest.key,
                'scope_type': cc.scope_type,
                'weight': cc.weight,
                'passing_grade': cc.passing_grade,
                'is_required': cc.is_required,
            }
        })


class CourseContestSearchAjax(LoginRequiredMixin, View):
    def get(self, request, slug):
        course = get_object_or_404(Course, key=slug)
        if not course.is_editable_by(request.user):
            raise PermissionDenied()

        q = request.GET.get('q', '').strip()
        contests = Contest.objects.all()
        if q:
            contests = contests.filter(Q(name__icontains=q) | Q(key__icontains=q))
        
        results = []
        for c in contests[:20]:
            results.append({
                'id': c.id,
                'key': c.key,
                'name': c.name,
                'is_visible': c.is_visible,
            })
        return JsonResponse({'results': results})


class ContestCreateCourse(CreateContest):
    permission_required = 'judge.create_private_contest'

    def dispatch(self, request, *args, **kwargs):
        self.course = get_object_or_404(Course, key=self.kwargs['slug'])
        if not self.course.is_editable_by(request.user):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial = initial.copy()
        prefix = ''.join(x for x in self.course.key.lower() if x.isalnum()) + '_'
        initial['key'] = f"{prefix}{timezone.now().strftime('%Y%m%d%H%M')}"
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['course_pk'] = self.course.pk
        return kwargs

    def save_contest_form(self, form):
        self.object = form.save()
        self.object.authors.add(self.request.profile)
        self.object.is_course_private = True
        self.object.is_course_only = True
        self.object.course = self.course
        self.object.save()

        CourseContest.objects.get_or_create(
            course=self.course,
            contest=self.object,
            defaults={'scope_type': CourseContest.SCOPE_COURSE}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contest_course'] = self.course
        context['course'] = self.course
        return context


class ContestEditCourse(EditContest):
    def dispatch(self, request, *args, **kwargs):
        self.course = get_object_or_404(Course, key=self.kwargs['slug'])
        if not self.course.is_editable_by(request.user):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['course_pk'] = self.course.pk
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contest_course'] = self.course
        context['course'] = self.course
        return context


