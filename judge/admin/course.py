from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from judge.models import Certificate, Chapter, Course, Enrollment, Exam, ExamProblem, Lesson, LessonProblem, LessonProgress


class LessonProblemInline(admin.TabularInline):
    model = LessonProblem
    extra = 1
    raw_id_fields = ('problem',)
    fields = ('problem', 'alias', 'custom_score', 'is_required_for_completion', 'order_index')


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 1
    fields = ('title', 'order_index')


class LessonInline(admin.StackedInline):
    model = Lesson
    extra = 1
    fields = ('title', 'order_index', 'is_published', 'estimated_minutes')


class ExamProblemInline(admin.TabularInline):
    model = ExamProblem
    extra = 1
    raw_id_fields = ('problem',)
    fields = ('problem', 'alias', 'custom_score', 'order_index', 'partial')


class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'key', 'instructor', 'status', 'is_public', 'order_index', 'created_at')
    list_filter = ('status', 'is_public', 'created_at')
    search_fields = ('title', 'key', 'description', 'instructor__user__username')
    prepopulated_fields = {'key': ('title',)}
    raw_id_fields = ('instructor',)
    inlines = [ChapterInline]


class ChapterAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order_index')
    list_filter = ('course',)
    search_fields = ('title', 'course__title')
    inlines = [LessonInline]


class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'chapter', 'order_index', 'is_published', 'estimated_minutes', 'created_at')
    list_filter = ('is_published', 'chapter__course')
    search_fields = ('title', 'chapter__title', 'chapter__course__title')
    inlines = [LessonProblemInline]


class ExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'chapter', 'target_type', 'exam_type', 'order_index', 'is_published')
    list_filter = ('target_type', 'exam_type', 'is_published', 'course')
    search_fields = ('title', 'course__title', 'chapter__title')
    raw_id_fields = ('contest',)
    inlines = [ExamProblemInline]


class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'lesson', 'is_completed', 'completed_at')
    list_filter = ('is_completed', 'lesson__chapter__course')
    search_fields = ('user__user__username', 'lesson__title')
    raw_id_fields = ('user', 'lesson')


class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'progress_percentage', 'status', 'enrolled_at', 'completed_at')
    list_filter = ('status', 'course')
    search_fields = ('user__user__username', 'course__title')
    raw_id_fields = ('user', 'course')


class CertificateAdmin(admin.ModelAdmin):
    list_display = ('cert_code', 'user', 'course', 'issued_by', 'issued_date', 'grade')
    list_filter = ('course', 'grade', 'issued_date')
    search_fields = ('cert_code', 'user__user__username', 'course__title', 'issued_by__user__username')
    raw_id_fields = ('user', 'course', 'issued_by')
