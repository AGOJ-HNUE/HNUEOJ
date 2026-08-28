import os
import sys
import json
import django

sys.path.insert(0, '/home/hnueoj/site')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dmoj.settings')
django.setup()

from django.conf import settings
settings.ALLOWED_HOSTS = ['*']

from django.contrib.auth.models import User
from django.utils import timezone
from judge.models import Course, Chapter, Contest, CourseContest, Enrollment, Profile, ContestParticipation, Problem

def run_audit():
    print("=== STARTING COURSE CONTEST INTEGRATION AUDIT ===")

    # 1. Create or get test user & profile
    user, _ = User.objects.get_or_create(username='audit_student_user')
    profile, _ = Profile.objects.get_or_create(user=user)

    teacher_user, _ = User.objects.get_or_create(username='audit_teacher_user')
    teacher_profile, _ = Profile.objects.get_or_create(user=teacher_user)

    # 2. Create Course & Chapter
    course, _ = Course.objects.get_or_create(
        key='audit-contest-course',
        defaults={'title': 'Khóa học Test Contest Integration', 'instructor': teacher_profile, 'status': Course.STATUS_PUBLISHED}
    )
    chapter, _ = Chapter.objects.get_or_create(
        course=course,
        title='Chương 1: Thuật toán cơ bản',
        defaults={'order_index': 1}
    )

    # 3. Create Chapter Contest & Course Contest
    contest_chap, _ = Contest.objects.get_or_create(
        key='ct-chap-1',
        defaults={
            'name': 'Contest Kiểm tra Chương 1',
            'start_time': timezone.now(),
            'end_time': timezone.now() + timezone.timedelta(days=30),
            'is_course_only': True,
        }
    )
    cc_chap, _ = CourseContest.objects.get_or_create(
        course=course,
        contest=contest_chap,
        defaults={'chapter': chapter, 'scope_type': CourseContest.SCOPE_CHAPTER, 'weight': 1.0, 'passing_grade': 50.0}
    )

    contest_final, _ = Contest.objects.get_or_create(
        key='ct-final-exam',
        defaults={
            'name': 'Contest Cuối khóa',
            'start_time': timezone.now(),
            'end_time': timezone.now() + timezone.timedelta(days=30),
            'is_course_only': True,
        }
    )
    cc_final, _ = CourseContest.objects.get_or_create(
        course=course,
        contest=contest_final,
        defaults={'chapter': None, 'scope_type': CourseContest.SCOPE_COURSE, 'weight': 2.0, 'passing_grade': 60.0}
    )

    print(f"[OK] Created Course '{course.title}' with {course.course_contests.count()} contests mapped.")
    assert course.total_contests_count == 2, f"Expected 2 contests, got {course.total_contests_count}"

    # 4. Student Enrollment & Progress Test
    enrollment, _ = Enrollment.objects.get_or_create(
        user=profile,
        course=course,
        defaults={'status': Enrollment.STATUS_ACTIVE}
    )

    progress = enrollment.recalculate_progress()
    print(f"[OK] Initial progress calculated: {progress}%")

    # 5. Simulate Contest Participation & Passed Grade
    part, _ = ContestParticipation.objects.get_or_create(
        contest=contest_chap,
        user=profile,
        defaults={'virtual': ContestParticipation.LIVE, 'cumtime': 100, 'score': 100}
    )

    passed_chap = cc_chap.is_passed_by(user)
    print(f"[OK] Chapter contest passed check by student: {passed_chap}")

    new_progress = enrollment.recalculate_progress()
    print(f"[OK] Progress after passing Chapter Contest (Progress Tracking Disabled): {new_progress}%")

    # 6. Test CourseContestDetailView Redirection & Auto-Registration via Client
    from django.test import Client
    client = Client()
    client.force_login(user)

    url = f"/course/{course.key}/contest/{cc_chap.id}/"
    resp = client.get(url, HTTP_HOST='localhost')
    print(f"[OK] GET {url} status code: {resp.status_code}, redirect location: {resp.headers.get('Location')}")
    assert resp.status_code == 302, f"Expected 302 redirect, got {resp.status_code}"
    assert f"/contest/{contest_chap.key}" in resp.headers.get('Location'), f"Expected redirect to /contest/{contest_chap.key}"

    # 7. Create Lesson & Test LessonLearnView Rendering
    from judge.models import Lesson
    lesson, _ = Lesson.objects.get_or_create(
        chapter=chapter,
        title='Bài 1: Nhập môn C++',
        defaults={'order_index': 1, 'is_published': True}
    )
    lesson_url = f"/course/{course.key}/learn/{lesson.id}/"
    resp_lesson = client.get(lesson_url, HTTP_HOST='localhost')
    print(f"[OK] GET {lesson_url} status code: {resp_lesson.status_code}")
    assert resp_lesson.status_code == 200, f"Expected 200 OK for lesson learn page, got {resp_lesson.status_code}"

    # 8. Test CourseManageView Rendering
    client.force_login(teacher_user)
    manage_url = f"/course/{course.key}/manage/"
    resp_manage = client.get(manage_url, HTTP_HOST='localhost')
    print(f"[OK] GET {manage_url} status code: {resp_manage.status_code}")
    assert resp_manage.status_code == 200, f"Expected 200 OK for course manage page, got {resp_manage.status_code}"

    # 9. Test CourseContest Item Deletion via DeleteCourseItemAjax
    del_url = f"/course/{course.key}/api/item/delete/"
    resp_del = client.post(del_url, data=json.dumps({'item_type': 'course_contest', 'item_id': cc_chap.id}), content_type='application/json', HTTP_HOST='localhost')
    print(f"[OK] POST {del_url} for course_contest status code: {resp_del.status_code}")
    assert resp_del.status_code == 200 and resp_del.json().get('success'), "DeleteCourseItemAjax for course_contest failed"
    assert not CourseContest.objects.filter(id=cc_chap.id).exists(), "CourseContest should be deleted"
    assert not Contest.objects.filter(id=contest_chap.id).exists(), "Course-only contest should be deleted when unmapped"

    # 10. Test Cascade Deletion when deleting Course and User
    course_id = course.id
    user_id = user.id
    course.delete()
    print(f"[OK] Course {course_id} deleted successfully.")
    assert not Course.objects.filter(id=course_id).exists(), "Course should be deleted"
    assert not CourseContest.objects.filter(course_id=course_id).exists(), "CourseContests should be cascade deleted"
    assert not Contest.objects.filter(id=contest_final.id).exists(), "Course-only final contest should be cascade deleted"

    user.delete()
    print(f"[OK] User {user_id} deleted successfully.")
    assert not Profile.objects.filter(id=profile.id).exists(), "User Profile should be cascade deleted"
    assert not Enrollment.objects.filter(user_id=profile.id).exists(), "Enrollments should be cascade deleted"

    print("=== COURSE CONTEST INTEGRATION & CASCADE DELETION AUDIT PASSED CLEANLY ===")

if __name__ == '__main__':
    run_audit()
