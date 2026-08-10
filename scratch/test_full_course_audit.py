import os
import sys
import django
import json

sys.path.insert(0, '/home/hnueoj/site')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dmoj.settings")
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User, AnonymousUser
from django.urls import reverse
from judge.models import Profile, Problem, Language, Submission, SubmissionSource
from judge.models.course import Course, Chapter, Lesson, Exam, ExamProblem, LessonProblem, Enrollment, LessonProgress, Certificate
from judge.views.course import (
    CourseListView, CourseDetailView, LessonLearnView, ExamDetailView,
    CourseManageView, CourseMonitorView, CertificateDetailView,
    SaveChapterAjax, SaveLessonAjax, SaveExamAjax,
    SaveLessonProblemAjax, SaveExamProblemAjax,
    LessonSubmitAjax, ExamSubmitView, ToggleLessonProgressAjax,
    DeleteCourseItemAjax, CourseMonitorDataAjax, SubmissionGodModeAjax
)

def run_system_audit():
    print("=== STARTING FULL COURSE / LMS SYSTEM AUDIT ===")
    factory = RequestFactory()

    # 1. Setup Test Users
    instructor_user, _ = User.objects.get_or_create(username='test_instructor_audit', defaults={'email': 'inst@test.com'})
    instructor_profile, _ = Profile.objects.get_or_create(user=instructor_user)
    
    student_user, _ = User.objects.get_or_create(username='test_student_audit', defaults={'email': 'student@test.com'})
    student_profile, _ = Profile.objects.get_or_create(user=student_user)

    # Clean previous test artifacts for idempotent runs
    Submission.objects.filter(user=student_profile).delete()
    Enrollment.objects.filter(user=student_profile).delete()
    LessonProgress.objects.filter(user=student_profile).delete()
    Course.objects.filter(key='audit-course').delete()

    # 2. Setup Test Problems and Language
    lang = Language.objects.first()
    from judge.models import ProblemGroup
    group = ProblemGroup.objects.first()
    prob1 = Problem.objects.filter(is_public=True).first()
    if not prob1:
        prob1 = Problem.objects.create(code='AUDIT_P1', name='Audit Problem 1', is_public=True, group=group, time_limit=1.0, memory_limit=262144)
    prob2 = Problem.objects.filter(is_public=False).first()
    if not prob2:
        prob2 = Problem.objects.create(code='AUDIT_P2', name='Audit Problem 2 (Private)', is_public=False, group=group, time_limit=1.0, memory_limit=262144)

    # 3. Setup Course
    course, _ = Course.objects.get_or_create(
        key='audit-course',
        defaults={
            'title': 'Audit Master Course',
            'description': 'Full LMS Audit Testing Course',
            'instructor': instructor_profile,
            'status': Course.STATUS_PUBLISHED,
        }
    )
    print(f"[OK] Course created/fetched: {course.title} (Instructor: {course.instructor_name})")

    # 4. Test Course Views as Anon, Student, Instructor
    # 4.1 CourseListView
    req = factory.get(reverse('course_list'))
    req.user = AnonymousUser()
    resp = CourseListView.as_view()(req)
    assert resp.status_code == 200, f"CourseListView failed: {resp.status_code}"
    print("[OK] CourseListView rendered 200 for AnonymousUser")

    # 4.2 CourseDetailView
    req = factory.get(reverse('course_detail', args=[course.key]))
    req.user = student_user
    req.profile = student_profile
    resp = CourseDetailView.as_view()(req, slug=course.key)
    assert resp.status_code == 200, f"CourseDetailView failed: {resp.status_code}"
    print("[OK] CourseDetailView rendered 200 for Student")

    # 5. AJAX: SaveChapterAjax
    req = factory.post(
        reverse('course_chapter_save', args=[course.key]),
        data=json.dumps({'title': 'Chương 1: Kiểm thử Tự động', 'description': 'Mô tả chương 1'}),
        content_type='application/json'
    )
    req.user = instructor_user
    req.profile = instructor_profile
    resp = SaveChapterAjax.as_view()(req, slug=course.key)
    assert resp.status_code == 200, f"SaveChapterAjax failed: {resp.content}"
    data = json.loads(resp.content)
    assert data.get('success') is True
    chapter_id = data['chapter']['id']
    chapter = Chapter.objects.get(id=chapter_id)
    print(f"[OK] SaveChapterAjax created chapter {chapter.title} (ID: {chapter.id})")

    # 6. AJAX: SaveLessonAjax
    req = factory.post(
        reverse('course_lesson_save', args=[course.key]),
        data=json.dumps({
            'chapter_id': chapter.id,
            'title': 'Bài 1: Giới thiệu LMS & Practice Problems',
            'content': '# Tiêu đề bài học\n\nNội dung lý thuyết $O(N)$',
            'video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'estimated_minutes': 20
        }),
        content_type='application/json'
    )
    req.user = instructor_user
    req.profile = instructor_profile
    resp = SaveLessonAjax.as_view()(req, slug=course.key)
    assert resp.status_code == 200, f"SaveLessonAjax failed: {resp.content}"
    data = json.loads(resp.content)
    assert data.get('success') is True
    lesson_id = data['lesson']['id']
    lesson = Lesson.objects.get(id=lesson_id)
    print(f"[OK] SaveLessonAjax created lesson {lesson.title} (ID: {lesson.id})")

    # 7. AJAX: SaveLessonProblemAjax & BatchSaveLessonProblemsAjax
    from judge.views.course import BatchSaveLessonProblemsAjax, BatchSaveExamProblemsAjax, CourseProblemSearchAjax

    # Test problem search
    req = factory.get(reverse('course_problem_search', args=[course.key]) + f'?q={prob1.code[:3]}')
    req.user = instructor_user
    req.profile = instructor_profile
    resp = CourseProblemSearchAjax.as_view()(req, slug=course.key)
    assert resp.status_code == 200, f"CourseProblemSearchAjax failed: {resp.content}"
    data = json.loads(resp.content)
    assert any(p['code'] == prob1.code for p in data['results']), f"Problem {prob1.code} should appear in search results"
    print(f"[OK] CourseProblemSearchAjax successfully found {len(data['results'])} problems matching search query")

    # Test BatchSaveLessonProblemsAjax (with drag-and-drop order)
    req = factory.post(
        reverse('course_lesson_problems_batch_save', args=[course.key, lesson.id]),
        data=json.dumps({
            'problems': [
                {'problem_code': prob1.code, 'is_required': True, 'order': 1},
                {'problem_code': prob2.code, 'is_required': False, 'order': 2},
            ]
        }),
        content_type='application/json'
    )
    req.user = instructor_user
    req.profile = instructor_profile
    resp = BatchSaveLessonProblemsAjax.as_view()(req, slug=course.key, lesson_id=lesson.id)
    assert resp.status_code == 200, f"BatchSaveLessonProblemsAjax failed: {resp.content}"
    assert lesson.lesson_problems.count() == 2
    lp1 = lesson.lesson_problems.get(problem=prob1)
    assert lp1.is_required_for_completion is True
    assert lp1.order_index == 1
    print(f"[OK] BatchSaveLessonProblemsAjax saved 2 ordered practice problems to lesson {lesson.id}")

    # 8. AJAX: SaveExamAjax
    req = factory.post(
        reverse('course_exam_save', args=[course.key]),
        data=json.dumps({
            'chapter_id': chapter.id,
            'title': 'Kỳ thi Đánh giá Chương 1',
            'description': 'Làm bài trong 60 phút',
            'exam_type': 'PRACTICE',
            'pass_percentage': 80
        }),
        content_type='application/json'
    )
    req.user = instructor_user
    req.profile = instructor_profile
    resp = SaveExamAjax.as_view()(req, slug=course.key)
    assert resp.status_code == 200, f"SaveExamAjax failed: {resp.content}"
    data = json.loads(resp.content)
    assert data.get('success') is True
    exam_id = data['exam']['id']
    exam = Exam.objects.get(id=exam_id)
    print(f"[OK] SaveExamAjax created exam {exam.title} (ID: {exam.id})")

    # 9. AJAX: BatchSaveExamProblemsAjax (with drag-and-drop order)
    req = factory.post(
        reverse('course_exam_problems_batch_save', args=[course.key, exam.id]),
        data=json.dumps({
            'problems': [
                {'problem_code': prob2.code, 'order': 1},
                {'problem_code': prob1.code, 'order': 2},
            ]
        }),
        content_type='application/json'
    )
    req.user = instructor_user
    req.profile = instructor_profile
    resp = BatchSaveExamProblemsAjax.as_view()(req, slug=course.key, exam_id=exam.id)
    assert resp.status_code == 200, f"BatchSaveExamProblemsAjax failed: {resp.content}"
    assert exam.exam_problems.count() == 2
    ep1 = exam.exam_problems.get(problem=prob2)
    assert ep1.order_index == 1
    print(f"[OK] BatchSaveExamProblemsAjax saved 2 ordered exam problems to exam {exam.id}")

    # 10. Student Enrollment & Permission Check
    enrollment, _ = Enrollment.objects.get_or_create(course=course, user=student_profile)
    print(f"[OK] Student enrolled in course. Status: {enrollment.status}, Progress: {enrollment.progress_percentage}%")
    
    # Check problem access for enrolled student on private problem attached to exam/lesson
    assert prob2.is_accessible_by(student_user) is True, "Student should have access to private problem attached to course exam"
    print("[OK] Private problem accessibility for enrolled student verified.")

    # 11. LessonLearnView & ExamDetailView rendering
    req = factory.get(reverse('course_lesson', args=[course.key, lesson.id]))
    req.user = student_user
    req.profile = student_profile
    resp = LessonLearnView.as_view()(req, slug=course.key, lesson_id=lesson.id)
    assert resp.status_code == 200, f"LessonLearnView failed: {resp.status_code}"
    print("[OK] LessonLearnView rendered 200")

    req = factory.get(reverse('course_exam', args=[course.key, exam.id]))
    req.user = student_user
    req.profile = student_profile
    resp = ExamDetailView.as_view()(req, slug=course.key, exam_id=exam.id)
    assert resp.status_code == 200, f"ExamDetailView rendered 200"
    print("[OK] ExamDetailView rendered 200")

    # 12. Quick Submit for Lesson
    req = factory.post(
        reverse('course_lesson_submit', args=[course.key, lesson.id]),
        data={
            'problem_code': prob1.code,
            'language': lang.key,
            'source': '#include <iostream>\nint main(){ std::cout << 42; return 0; }'
        }
    )
    req.user = student_user
    req.profile = student_profile
    resp = LessonSubmitAjax.as_view()(req, slug=course.key, lesson_id=lesson.id)
    assert resp.status_code == 200, f"LessonSubmitAjax failed: {resp.content}"
    data = json.loads(resp.content)
    assert data.get('success') is True
    sub_lesson_id = data['submission_id']
    sub_lesson = Submission.objects.get(id=sub_lesson_id)
    assert sub_lesson.lesson == lesson, "Submission must link to lesson"
    print(f"[OK] LessonSubmitAjax created submission #{sub_lesson_id} linked to Lesson #{lesson.id}")

    # 13. Quick Submit for Exam (GET and POST)
    req = factory.get(reverse('course_exam_submit', args=[course.key, exam.id]))
    req.user = student_user
    req.profile = student_profile
    resp = ExamSubmitView.as_view()(req, slug=course.key, exam_id=exam.id)
    assert resp.status_code == 302, f"ExamSubmitView GET should redirect: {resp.status_code}"
    print("[OK] ExamSubmitView GET redirects cleanly without 405 error")

    req = factory.post(
        reverse('course_exam_submit', args=[course.key, exam.id]),
        data={
            'problem_code': prob2.code,
            'language': lang.key,
            'source': '#include <iostream>\nint main(){ std::cout << 100; return 0; }'
        }
    )
    req.user = student_user
    req.profile = student_profile
    resp = ExamSubmitView.as_view()(req, slug=course.key, exam_id=exam.id)
    assert resp.status_code == 200, f"ExamSubmitView POST failed: {resp.content}"
    data = json.loads(resp.content)
    assert data.get('success') is True
    sub_exam_id = data['submission_id']
    sub_exam = Submission.objects.get(id=sub_exam_id)
    assert sub_exam.exam == exam, "Submission must link to exam"
    print(f"[OK] ExamSubmitView created submission #{sub_exam_id} linked to Exam #{exam.id}")

    # 14. Smart Lesson Progress Toggle Lock check
    req = factory.post(
        reverse('course_lesson_toggle', args=[course.key, lesson.id]),
        data=json.dumps({}),
        content_type='application/json'
    )
    req.user = student_user
    req.profile = student_profile
    resp = ToggleLessonProgressAjax.as_view()(req, slug=course.key, lesson_id=lesson.id)
    assert resp.status_code == 400, f"ToggleLessonProgressAjax should fail if required problem is not AC: {resp.content}"
    print("[OK] Smart Lesson completion lock correctly blocked completion without AC on required practice problem")

    # Mark submission as AC and test completion
    sub_lesson.result = 'AC'
    sub_lesson.points = 100
    sub_lesson.status = 'D'
    sub_lesson.save()

    resp = ToggleLessonProgressAjax.as_view()(req, slug=course.key, lesson_id=lesson.id)
    assert resp.status_code == 200, f"ToggleLessonProgressAjax failed after AC: {resp.content}"
    data = json.loads(resp.content)
    assert data.get('is_completed') is True
    print("[OK] ToggleLessonProgressAjax marked lesson completed after student achieved AC")

    # 15. Live Monitor (God-Mode)
    req = factory.get(reverse('course_monitor', args=[course.key]))
    req.user = instructor_user
    req.profile = instructor_profile
    resp = CourseMonitorView.as_view()(req, slug=course.key)
    assert resp.status_code == 200, f"CourseMonitorView failed: {resp.status_code}"
    print("[OK] CourseMonitorView rendered 200")

    req = factory.get(reverse('course_monitor_data', args=[course.key]))
    req.user = instructor_user
    req.profile = instructor_profile
    resp = CourseMonitorDataAjax.as_view()(req, slug=course.key)
    assert resp.status_code == 200, f"CourseMonitorDataAjax failed: {resp.content}"
    data = json.loads(resp.content)
    assert len(data['recent_submissions']) >= 2, "Both lesson and exam submissions should be visible in Monitor data"
    print(f"[OK] CourseMonitorDataAjax retrieved {len(data['recent_submissions'])} recent submissions (both lesson & exam)")

    req = factory.get(reverse('course_submission_god_mode', args=[course.key, sub_lesson.id]))
    req.user = instructor_user
    req.profile = instructor_profile
    resp = SubmissionGodModeAjax.as_view()(req, slug=course.key, submission_id=sub_lesson.id)
    assert resp.status_code == 200, f"SubmissionGodModeAjax failed for lesson submission: {resp.content}"
    print(f"[OK] SubmissionGodModeAjax loaded lesson submission source and details cleanly")

    # 16. CourseManageView test
    req = factory.get(reverse('course_manage', args=[course.key]))
    req.user = instructor_user
    req.profile = instructor_profile
    resp = CourseManageView.as_view()(req, slug=course.key)
    assert resp.status_code == 200, f"CourseManageView failed: {resp.status_code}"
    print("[OK] CourseManageView rendered 200 for Instructor")

    # 17. Certificate Generation and View
    cert, _ = Certificate.objects.get_or_create(
        course=course,
        user=student_profile,
        defaults={
            'grade': 'Xuất sắc (Excellent)',
            'issued_by': instructor_profile
        }
    )
    req = factory.get(reverse('certificate_detail', args=[cert.cert_code]))
    req.user = student_user
    req.profile = student_profile
    resp = CertificateDetailView.as_view()(req, cert_code=cert.cert_code)
    assert resp.status_code == 200, f"CertificateDetailView failed: {resp.status_code}"
    print(f"[OK] CertificateDetailView rendered 200 for cert {cert.cert_code}")

    from judge.views.course import CertificatePdfView
    req = factory.get(reverse('certificate_pdf', args=[cert.cert_code]))
    req.user = student_user
    req.profile = student_profile
    resp = CertificatePdfView.as_view()(req, cert_code=cert.cert_code)
    assert resp.status_code == 200, f"CertificatePdfView failed: {resp.status_code}"
    print(f"[OK] CertificatePdfView rendered 200 for cert {cert.cert_code}")

    print("\n==========================================")
    print("ALL LMS MODULE AUDIT CHECKS PASSED PERFECTLY!")
    print("==========================================")

if __name__ == '__main__':
    run_system_audit()
