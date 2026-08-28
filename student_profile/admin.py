from django.contrib import admin
from .models import Semester, Subject, StudentGrade


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'academic_year', 'order', 'created_at')
    search_fields = ('id', 'name', 'academic_year')
    list_filter = ('academic_year',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'credits', 'difficulty', 'department')
    list_editable = ('difficulty', 'credits')
    search_fields = ('code', 'name', 'department')
    list_filter = ('difficulty', 'credits', 'department')
    ordering = ('code',)


@admin.register(StudentGrade)
class StudentGradeAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'semester', 'letter_grade', 'score_4', 'updated_at')
    search_fields = ('user__username', 'subject__code', 'subject__name')
    list_filter = ('semester', 'letter_grade')
    raw_id_fields = ('user',)
