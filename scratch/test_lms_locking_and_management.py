import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dmoj.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from judge.models import Course, Chapter, Lesson, Exam, Enrollment, Profile
from judge.views.course import (
    CourseListView,
    CourseDetailView,
    CourseManageView,
    LessonLearnView,
    ExamDetailView,
    SaveCourseInfoAjax,
    ToggleCourseItemLockAjax,
    SaveLessonAjax,
    SaveExamAjax
)

def create_request(factory, method, path, user=None, data=None):
    if method == 'GET':
        req = factory.get(path)
    else:
        req = factory.post(path, data=json.dumps(data) if isinstance(data, dict) else data, content_type='application/json')
    req.user = user or AnonymousUser()
    req.profile = getattr(user, 'profile', None) if user and user.is_authenticated else None
    req.LANGUAGE_CODE = 'vi'
    req.in_contest = False
    req.official_contest_mode = False
    req.misc_config = {}
    setattr(req, 'session', 'session')
    messages = FallbackStorage(req)
    setattr(req, '_messages', messages)
    return req

def run_tests():
    factory = RequestFactory()
    
    # 1. Setup users
    teacher_user, _ = User.objects.get_or_create(username='test_teacher', defaults={'email': 'teacher@test.com'})
    teacher_profile, _ = Profile.objects.get_or_create(user=teacher_user)
    
    student_user, _ = User.objects.get_or_create(username='test_student', defaults={'email': 'student@test.com'})
    student_profile, _ = Profile.objects.get_or_create(user=student_user)
    
    stranger_user, _ = User.objects.get_or_create(username='test_stranger', defaults={'email': 'stranger@test.com'})
    stranger_profile, _ = Profile.objects.get_or_create(user=stranger_user)

    # 2. Setup Course
    course, _ = Course.objects.get_or_create(
        key='test-lock-course',
        defaults={
            'title': 'Khóa học Test Khóa & Học phí',
            'instructor': teacher_profile,
            'price': 500000,
            'status': Course.STATUS_PUBLISHED,
            'is_public': True,
            'is_locked': False
        }
    )
    course.price = 500000
    course.is_locked = False
    course.save()

    print(f"[TEST 1] Formatted price: {course.formatted_price} (expected: 500.000 đ)")
    assert '500.000' in course.formatted_price

    # Setup Chapter
    chapter, _ = Chapter.objects.get_or_create(course=course, title='Chương 1: Test')
    
    # Setup Lesson 1 (Unlocked) and Lesson 2 (Locked)
    lesson1, _ = Lesson.objects.get_or_create(chapter=chapter, title='Bài 1 Mở', defaults={'is_locked': False, 'is_published': True})
    lesson1.is_locked = False
    lesson1.is_published = True
    lesson1.save()

    lesson2, _ = Lesson.objects.get_or_create(chapter=chapter, title='Bài 2 Khóa', defaults={'is_locked': True, 'is_published': True})
    lesson2.is_locked = True
    lesson2.is_published = True
    lesson2.save()

    # Setup Exam 1 (Unlocked) and Exam 2 (Locked)
    exam1, _ = Exam.objects.get_or_create(course=course, chapter=chapter, title='Thi 1 Mở', defaults={'is_locked': False, 'is_published': True})
    exam1.is_locked = False
    exam1.is_published = True
    exam1.save()

    exam2, _ = Exam.objects.get_or_create(course=course, chapter=chapter, title='Thi 2 Khóa', defaults={'is_locked': True, 'is_published': True})
    exam2.is_locked = True
    exam2.is_published = True
    exam2.save()

    # Enroll student only, NOT stranger
    Enrollment.objects.filter(course=course, user=stranger_profile).delete()
    enrollment, _ = Enrollment.objects.get_or_create(course=course, user=student_profile, defaults={'status': Enrollment.STATUS_ACTIVE})

    # Test stranger accessing lesson1 -> Should redirect to course_detail
    req = create_request(factory, 'GET', f'/course/{course.key}/learn/{lesson1.id}/', user=stranger_user)
    resp = LessonLearnView.as_view()(req, slug=course.key, lesson_id=lesson1.id)
    print(f"[TEST 2] Stranger access lesson1 status: {resp.status_code} (Redirect: {resp.url if hasattr(resp, 'url') else 'N/A'})")
    assert resp.status_code == 302, "Non-enrolled user must be redirected away from lesson"

    # Test stranger accessing exam1 -> Should redirect to course_detail
    req = create_request(factory, 'GET', f'/course/{course.key}/exam/{exam1.id}/', user=stranger_user)
    resp = ExamDetailView.as_view()(req, slug=course.key, exam_id=exam1.id)
    print(f"[TEST 3] Stranger access exam1 status: {resp.status_code} (Redirect: {resp.url if hasattr(resp, 'url') else 'N/A'})")
    assert resp.status_code == 302, "Non-enrolled user must be redirected away from exam"

    # Test enrolled student accessing lesson1 (Unlocked) -> 200 OK
    req = create_request(factory, 'GET', f'/course/{course.key}/learn/{lesson1.id}/', user=student_user)
    resp = LessonLearnView.as_view()(req, slug=course.key, lesson_id=lesson1.id)
    rendered = resp.render()
    print(f"[TEST 4] Student access unlocked lesson1: {resp.status_code} (Length: {len(rendered.content)})")
    assert resp.status_code == 200

    # Test enrolled student accessing lesson2 (Locked) -> Should redirect to course_detail
    req = create_request(factory, 'GET', f'/course/{course.key}/learn/{lesson2.id}/', user=student_user)
    resp = LessonLearnView.as_view()(req, slug=course.key, lesson_id=lesson2.id)
    print(f"[TEST 5] Student access locked lesson2: {resp.status_code} (Redirect: {resp.url if hasattr(resp, 'url') else 'N/A'})")
    assert resp.status_code == 302, "Enrolled student must be blocked from locked lesson"

    # Test teacher accessing lesson2 (Locked) -> 200 OK
    req = create_request(factory, 'GET', f'/course/{course.key}/learn/{lesson2.id}/', user=teacher_user)
    resp = LessonLearnView.as_view()(req, slug=course.key, lesson_id=lesson2.id)
    rendered = resp.render()
    print(f"[TEST 6] Teacher access locked lesson2: {resp.status_code} (Length: {len(rendered.content)})")
    assert resp.status_code == 200

    # Test teacher toggle lock Ajax for lesson1
    req = create_request(factory, 'POST', f'/course/{course.key}/api/item/toggle-lock/', user=teacher_user, data={'item_type': 'lesson', 'item_id': lesson1.id})
    resp = ToggleCourseItemLockAjax.as_view()(req, slug=course.key)
    res_data = json.loads(resp.content.decode('utf-8'))
    print(f"[TEST 7] Toggle lock lesson1: {res_data}")
    assert res_data.get('is_locked') == True
    lesson1.refresh_from_db()
    assert lesson1.is_locked == True

    # Test teacher save course info Ajax (Edit price, title, is_locked)
    req = create_request(factory, 'POST', f'/course/{course.key}/api/course/save/', user=teacher_user, data={
        'title': 'Khóa học Đã đổi tên & Học phí mới',
        'price': 1200000,
        'status': 'PUBLISHED',
        'is_public': True,
        'is_locked': False,
        'description': 'Mô tả mới toanh',
        'thumbnail_url': 'https://example.com/thumb.jpg'
    })
    resp = SaveCourseInfoAjax.as_view()(req, slug=course.key)
    res_data = json.loads(resp.content.decode('utf-8'))
    print(f"[TEST 8] Save Course Info Ajax: {res_data}")
    assert res_data.get('success') == True
    course.refresh_from_db()
    assert course.price == 1200000
    assert course.title == 'Khóa học Đã đổi tên & Học phí mới'
    assert '1.200.000' in course.formatted_price

    # Test CourseManageView rendering
    req = create_request(factory, 'GET', f'/course/{course.key}/manage/', user=teacher_user)
    resp = CourseManageView.as_view()(req, slug=course.key)
    rendered = resp.render()
    print(f"[TEST 9] CourseManageView render: {resp.status_code} (Length: {len(rendered.content)})")
    assert resp.status_code == 200

    # Test CourseDetailView rendering for stranger
    req = create_request(factory, 'GET', f'/course/{course.key}/', user=stranger_user)
    resp = CourseDetailView.as_view()(req, slug=course.key)
    rendered = resp.render()
    print(f"[TEST 10] CourseDetailView stranger render: {resp.status_code} (Length: {len(rendered.content)})")
    assert resp.status_code == 200
    assert '1.200.000' in rendered.content.decode('utf-8')
    assert 'Cần ghi danh' in rendered.content.decode('utf-8')

    # Test CourseListView rendering
    req = create_request(factory, 'GET', '/courses/', user=stranger_user)
    resp = CourseListView.as_view()(req)
    rendered = resp.render()
    print(f"[TEST 11] CourseListView render: {resp.status_code} (Length: {len(rendered.content)})")
    assert resp.status_code == 200
    assert '1.200.000' in rendered.content.decode('utf-8')

    print("\nALL TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run_tests()
