from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.contrib.flatpages.models import FlatPage

from judge.admin.comments import CommentAdmin
from judge.admin.contest import ContestAdmin, ContestParticipationAdmin, ContestTagAdmin
from judge.admin.interface import BlogPostAdmin, BlogPostTagAdmin, FlatPageAdmin, LicenseAdmin, LogEntryAdmin, \
    NavigationBarAdmin
from judge.admin.organization import OrganizationAdmin, OrganizationRequestAdmin
from judge.admin.problem import ProblemAdmin
from judge.admin.profile import ProfileAdmin, UserAdmin
from judge.admin.runtime import JudgeAdmin, LanguageAdmin
from judge.admin.submission import SubmissionAdmin
from judge.admin.tag import TagAdmin, TagGroupAdmin, TagProblemAdmin
from judge.admin.taxon import ProblemGroupAdmin, ProblemTypeAdmin
from judge.admin.ticket import TicketAdmin
from judge.admin.course import CertificateAdmin, ChapterAdmin, CourseAdmin, EnrollmentAdmin, ExamAdmin, \
    LessonAdmin, LessonProgressAdmin
from judge.models import Badge, BlogPost, BlogPostTag, Certificate, Chapter, Comment, CommentLock, Contest, \
    ContestParticipation, ContestTag, Course, Enrollment, Exam, Judge, Language, Lesson, LessonProgress, \
    License, MiscConfig, NavigationBar, Organization, OrganizationRequest, Problem, ProblemGroup, ProblemType, \
    Profile, Submission, Tag, TagGroup, TagProblem, Ticket

admin.site.register(Course, CourseAdmin)
admin.site.register(Chapter, ChapterAdmin)
admin.site.register(Lesson, LessonAdmin)
admin.site.register(Exam, ExamAdmin)
admin.site.register(LessonProgress, LessonProgressAdmin)
admin.site.register(Enrollment, EnrollmentAdmin)
admin.site.register(Certificate, CertificateAdmin)
admin.site.register(BlogPost, BlogPostAdmin)
admin.site.register(BlogPostTag, BlogPostTagAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(CommentLock)
admin.site.register(Contest, ContestAdmin)
admin.site.register(ContestParticipation, ContestParticipationAdmin)
admin.site.register(ContestTag, ContestTagAdmin)
admin.site.unregister(FlatPage)
admin.site.register(FlatPage, FlatPageAdmin)
admin.site.register(Judge, JudgeAdmin)
admin.site.register(Language, LanguageAdmin)
admin.site.register(License, LicenseAdmin)
admin.site.register(LogEntry, LogEntryAdmin)
admin.site.register(MiscConfig)
admin.site.register(Badge)
admin.site.register(NavigationBar, NavigationBarAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(OrganizationRequest, OrganizationRequestAdmin)
admin.site.register(Problem, ProblemAdmin)
admin.site.register(ProblemGroup, ProblemGroupAdmin)
admin.site.register(ProblemType, ProblemTypeAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(Submission, SubmissionAdmin)
admin.site.register(Ticket, TicketAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(TagGroup, TagGroupAdmin)
admin.site.register(TagProblem, TagProblemAdmin)
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
