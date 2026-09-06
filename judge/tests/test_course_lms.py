import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from judge.models import (
    Certificate,
    Chapter,
    Contest,
    Course,
    CourseContest,
    Enrollment,
    Exam,
    ExamProblem,
    Language,
    Lesson,
    LessonProgress,
    Problem,
    ProblemGroup,
    ProblemType,
    Profile,
    Submission,
    SubmissionSource,
)


class CourseLMSTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.password = 'password123'

        # Instructor
        cls.instructor_user = user_model.objects.create_user(username='instructor1', password=cls.password)
        cls.instructor_profile = Profile.objects.create(user=cls.instructor_user)

        # Student 1
        cls.student_user = user_model.objects.create_user(username='student1', password=cls.password)
        cls.student_profile = Profile.objects.create(user=cls.student_user)

        # Student 2
        cls.student2_user = user_model.objects.create_user(username='student2', password=cls.password)
        cls.student2_profile = Profile.objects.create(user=cls.student2_user)

        # System dependencies
        cls.group = ProblemGroup.objects.create(name='default-group', full_name='Default Group')
        cls.ptype = ProblemType.objects.create(name='algo', full_name='Algorithms')
        cls.language = Language.objects.create(
            key='CPP20',
            name='C++ 20',
            short_name='C++20',
            common_name='C++',
            ace='c_cpp',
            pygments='cpp',
            extension='cpp',
        )

        # Problems
        cls.public_problem = Problem.objects.create(
            code='apb',
            name='A Plus B',
            is_public=True,
            points=100,
            time_limit=1.0,
            memory_limit=65536,
            group=cls.group,
        )
        cls.private_problem = Problem.objects.create(
            code='priv_segtree',
            name='Private Segment Tree',
            is_public=False,
            points=100,
            time_limit=1.0,
            memory_limit=65536,
            group=cls.group,
        )

        # Course
        cls.course = Course.objects.create(
            key='cpp-algo',
            title='C++ và Thuật toán',
            description='Khóa học thuật toán từ cơ bản đến nâng cao.',
            status=Course.STATUS_PUBLISHED,
            instructor=cls.instructor_profile,
            is_public=True,
        )
        cls.course.instructors.add(cls.instructor_profile)

        # Chapters & Lessons
        cls.chapter1 = Chapter.objects.create(
            course=cls.course,
            title='Chương 1: Cơ bản',
            order_index=1,
        )
        cls.lesson1 = Lesson.objects.create(
            chapter=cls.chapter1,
            title='Bài 1: Nhập xuất',
            content='# Nhập xuất trong C++',
            order_index=1,
        )
        cls.lesson2 = Lesson.objects.create(
            chapter=cls.chapter1,
            title='Bài 2: Con trỏ',
            content='# Con trỏ',
            order_index=2,
        )

        # Exam with Private problem
        cls.exam1 = Exam.objects.create(
            course=cls.course,
            chapter=cls.chapter1,
            title='Kiểm tra Chương 1',
            target_type=Exam.TARGET_CHAPTER,
            exam_type=Exam.TYPE_PRACTICE,
            pass_percentage=60.0,
            order_index=1,
        )
        cls.exam_problem = ExamProblem.objects.create(
            exam=cls.exam1,
            problem=cls.private_problem,
            alias='Bài kiểm tra 1 (Tùy biến)',
            custom_score=50.0,
            order_index=1,
        )

    def test_course_creation_and_urls(self):
        """Kiểm tra tạo khóa học và các URL hợp lệ"""
        self.assertEqual(self.course.student_count, 0)
        self.assertEqual(self.course.total_lessons_count, 2)
        self.assertEqual(self.course.total_exams_count, 1)
        self.assertTrue(self.course.is_accessible_by(self.student_user))
        self.assertTrue(self.course.is_editable_by(self.instructor_user))
        self.assertFalse(self.course.is_editable_by(self.student_user))

    def test_enrollment_and_progress_flow(self):
        """Kiểm tra ghi danh và tính toán % hoàn thành tiến độ học"""
        enrollment = Enrollment.objects.create(
            user=self.student_profile,
            course=self.course,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.assertEqual(enrollment.progress_percentage, 0.0)

        # Complete lesson 1 (1 out of 3 total items: 2 lessons + 1 exam)
        LessonProgress.objects.create(
            user=self.student_profile,
            lesson=self.lesson1,
            is_completed=True,
            completed_at=timezone.now(),
        )
        pct = enrollment.recalculate_progress()
        self.assertAlmostEqual(pct, 33.3, places=1)
        self.assertEqual(enrollment.status, Enrollment.STATUS_ACTIVE)

        # Complete lesson 2
        LessonProgress.objects.create(
            user=self.student_profile,
            lesson=self.lesson2,
            is_completed=True,
            completed_at=timezone.now(),
        )
        pct = enrollment.recalculate_progress()
        self.assertAlmostEqual(pct, 66.7, places=1)

        # Submit to exam to pass (score 50/50 -> 100% on exam)
        sub = Submission.objects.create(
            user=self.student_profile,
            problem=self.private_problem,
            language=self.language,
            exam=self.exam1,
            points=100.0,
            result='AC',
            status='D',
        )
        pct = enrollment.recalculate_progress()
        self.assertEqual(pct, 100.0)
        # Should automatically transition to READY_FOR_REVIEW
        self.assertEqual(enrollment.status, Enrollment.STATUS_READY_FOR_REVIEW)

    def test_private_problem_access_for_enrolled_student(self):
        """Kiểm tra học viên ghi danh được quyền truy cập bài Private thuộc kỳ thi khóa học"""
        # Before enrollment: cannot access private problem
        self.assertFalse(self.private_problem.is_accessible_by(self.student2_user))

        # Enrolled student: can access
        Enrollment.objects.create(
            user=self.student_profile,
            course=self.course,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.assertTrue(self.private_problem.is_accessible_by(self.student_user))

    def test_exam_problem_alias_and_custom_score(self):
        """Kiểm tra hiển thị Alias và Custom Score của bài tập trong kỳ thi"""
        self.assertEqual(self.exam_problem.display_title, 'Bài kiểm tra 1 (Tùy biến)')
        self.assertEqual(self.exam_problem.display_points, 50.0)

    def test_toggle_lesson_progress_api(self):
        """Kiểm tra API AJAX toggle hoàn thành bài học"""
        self.client.login(username='student1', password=self.password)
        # Enroll first
        Enrollment.objects.create(user=self.student_profile, course=self.course)

        url = reverse('course_lesson_toggle', args=[self.course.key, self.lesson1.id])
        response = self.client.post(url, data=json.dumps({}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['is_completed'])

        # Toggle again to uncomplete
        response2 = self.client.post(url, data=json.dumps({}), content_type='application/json')
        data2 = response2.json()
        self.assertFalse(data2['is_completed'])

    def test_certificate_issuance(self):
        """Kiểm tra quy trình cấp chứng chỉ khi tiến độ đạt từ 80% trở lên"""
        enrollment = Enrollment.objects.create(
            user=self.student_profile,
            course=self.course,
            status=Enrollment.STATUS_ACTIVE,
        )

        # Try to issue certificate when < 80%: should fail
        self.client.login(username='instructor1', password=self.password)
        cert_url = reverse('course_issue_certificate', args=[self.course.key, enrollment.id])
        resp = self.client.post(cert_url, data=json.dumps({'grade': 'Xuất sắc'}), content_type='application/json')
        self.assertEqual(resp.status_code, 400)

        # Complete everything
        LessonProgress.objects.create(user=self.student_profile, lesson=self.lesson1, is_completed=True)
        LessonProgress.objects.create(user=self.student_profile, lesson=self.lesson2, is_completed=True)
        Submission.objects.create(
            user=self.student_profile,
            problem=self.private_problem,
            language=self.language,
            exam=self.exam1,
            points=100.0,
            result='AC',
            status='D',
        )
        enrollment.recalculate_progress()

        # Issue certificate successfully
        resp2 = self.client.post(cert_url, data=json.dumps({'grade': 'Xuất sắc'}), content_type='application/json')
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertTrue(data2['success'])
        self.assertTrue(data2['cert_code'].startswith('VNOJ-CERT-'))

        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, Enrollment.STATUS_COMPLETED)

        # Verify public certificate detail view
        cert_detail_url = reverse('certificate_detail', args=[data2['cert_code']])
        view_resp = self.client.get(cert_detail_url)
        self.assertEqual(view_resp.status_code, 200)
        self.assertContains(view_resp, self.student_user.username)
        self.assertContains(view_resp, self.course.title)

    def test_god_mode_drill_down_api(self):
        """Kiểm tra API God-Mode Drill Down lấy chi tiết bài nộp cho giảng viên"""
        sub = Submission.objects.create(
            user=self.student_profile,
            problem=self.private_problem,
            language=self.language,
            exam=self.exam1,
            points=100.0,
            result='AC',
            status='D',
        )
        SubmissionSource.objects.create(
            submission=sub,
            source='#include <iostream>\nint main(){ std::cout << "Hello"; }\n',
        )

        # Student cannot access god-mode
        self.client.login(username='student1', password=self.password)
        god_url = reverse('course_submission_god_mode', args=[self.course.key, sub.id])
        resp_student = self.client.get(god_url)
        self.assertEqual(resp_student.status_code, 403)

        # Instructor can access god-mode
        self.client.login(username='instructor1', password=self.password)
        resp_instructor = self.client.get(god_url)
        self.assertEqual(resp_instructor.status_code, 200)
        data = resp_instructor.json()
        self.assertEqual(data['submission']['id'], sub.id)
        self.assertIn('std::cout', data['submission']['source'])

    def test_lesson_practice_problem_management(self):
        """Kiểm tra Giảng viên thêm, sửa, xóa LessonProblem qua API"""
        self.client.login(username='instructor1', password=self.password)

        save_url = reverse('course_lesson_problem_save', args=[self.course.key])
        resp = self.client.post(save_url, data=json.dumps({
            'lesson_id': self.lesson1.id,
            'problem_code': self.public_problem.code,
            'alias': 'Bài thực hành A+B',
            'custom_score': 50.0,
            'is_required_for_completion': True,
            'order_index': 1,
        }), content_type='application/json')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['problem']['code'], self.public_problem.code)
        self.assertEqual(data['problem']['name'], 'Bài thực hành A+B')
        self.assertEqual(data['problem']['points'], 50.0)
        self.assertTrue(data['problem']['is_required_for_completion'])

        # Delete lesson problem
        del_url = reverse('course_item_delete', args=[self.course.key])
        del_resp = self.client.post(del_url, data=json.dumps({
            'item_type': 'lesson_problem',
            'item_id': data['problem']['id'],
        }), content_type='application/json')
        self.assertEqual(del_resp.status_code, 200)

    def test_lesson_practice_problem_submission_and_completion_lock(self):
        """Kiểm tra quy trình nộp bài thực hành bài học và khóa hoàn thành thông minh"""
        from judge.models.course import LessonProblem
        # Gán bài tập bắt buộc vào Lesson 1
        lp = LessonProblem.objects.create(
            lesson=self.lesson1,
            problem=self.public_problem,
            alias='Thực hành 1',
            is_required_for_completion=True,
            order_index=1,
        )

        self.client.login(username='student1', password=self.password)
        Enrollment.objects.create(user=self.student_profile, course=self.course)

        # 1. Thử đánh dấu hoàn thành khi chưa AC: phải bị chặn (400)
        toggle_url = reverse('course_lesson_toggle', args=[self.course.key, self.lesson1.id])
        resp = self.client.post(toggle_url, data=json.dumps({'completed': True}), content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data.get('can_complete', True))

        # 2. Nộp bài thực hành qua API Lesson Submit
        submit_url = reverse('course_lesson_submit', args=[self.course.key, self.lesson1.id])
        sub_resp = self.client.post(submit_url, data={
            'problem_code': self.public_problem.code,
            'language': self.language.key,
            'source': '#include <iostream>\nint main(){ int a, b; std::cin >> a >> b; std::cout << a+b; }\n',
        })
        self.assertEqual(sub_resp.status_code, 200)
        sub_data = sub_resp.json()
        self.assertTrue(sub_data['success'])
        sub_id = sub_data['submission_id']

        sub = Submission.objects.get(id=sub_id)
        self.assertEqual(sub.lesson_id, self.lesson1.id)
        self.assertEqual(sub.user_id, self.student_profile.id)

        # 3. Giả lập máy chấm trả về AC
        sub.status = 'D'
        sub.result = 'AC'
        sub.points = 100.0
        sub.save()

        # 4. Đánh dấu hoàn thành lại: phải thành công
        resp_after = self.client.post(toggle_url, data=json.dumps({'completed': True}), content_type='application/json')
        self.assertEqual(resp_after.status_code, 200)
        self.assertTrue(resp_after.json()['is_completed'])

    def test_private_problem_accessible_via_lesson_problem(self):
        """Kiểm tra bài Private mở quyền truy cập cho học viên ghi danh qua LessonProblem"""
        from judge.models.course import LessonProblem
        LessonProblem.objects.create(
            lesson=self.lesson1,
            problem=self.private_problem,
            is_required_for_completion=False,
        )

        # Chưa ghi danh: không truy cập được
        self.assertFalse(self.private_problem.is_accessible_by(self.student_user))

        # Đã ghi danh: có quyền truy cập
        Enrollment.objects.create(user=self.student_profile, course=self.course, status=Enrollment.STATUS_ACTIVE)
        self.assertTrue(self.private_problem.is_accessible_by(self.student_user))

    def test_multiple_instructors_permissions_and_save(self):
        """Kiểm tra tính năng nhiều giảng viên phụ trách khóa học"""
        user_model = get_user_model()
        co_instructor_user = user_model.objects.create_user(username='instructor2', password=self.password)
        co_instructor_profile = Profile.objects.create(user=co_instructor_user)

        # 1. Giảng viên 2 chưa được thêm vào course: không có quyền edit
        self.assertFalse(self.course.is_editable_by(co_instructor_user))

        # 2. Thêm giảng viên 2 vào instructors ManyToMany
        self.course.instructors.add(self.instructor_profile, co_instructor_profile)

        # Giảng viên 2 giờ đây có quyền edit và truy cập bài học locked
        self.assertTrue(self.course.is_editable_by(co_instructor_user))
        self.assertTrue(self.lesson1.is_accessible_by(co_instructor_user))
        self.assertIn('instructor1', self.course.instructor_name)
        self.assertIn('instructor2', self.course.instructor_name)

        # 3. Cập nhật danh sách giảng viên qua AJAX SaveCourseInfoAjax
        self.client.login(username='instructor1', password=self.password)
        save_url = reverse('course_info_save', args=[self.course.key])
        resp = self.client.post(
            save_url,
            data=json.dumps({
                'title': self.course.title,
                'instructor_usernames': 'instructor1, instructor2',
                'price': 0,
                'status': 'PUBLISHED',
            }),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['course']['instructors']), 2)

    def test_course_contest_displayed_without_chapters(self):
        """Kiểm tra Contest khóa học vẫn hiển thị ở trang chủ khóa học dù chưa có chương nào"""
        c_empty = Course.objects.create(
            key='empty-course',
            title='Khóa học Chưa có Chương',
            author=self.instructor_profile,
            is_public=True,
        )
        contest = Contest.objects.create(
            key='empty_course_ct',
            name='Contest Giữa kỳ Khóa Empty',
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(days=7),
            is_visible=True,
            course=c_empty,
        )
        CourseContest.objects.create(
            course=c_empty,
            contest=contest,
            scope_type=CourseContest.SCOPE_COURSE,
        )

        resp = self.client.get(reverse('course_detail', args=[c_empty.key]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Contest Giữa kỳ Khóa Empty', content)
        self.assertIn('Contest Khóa học', content)

    def test_reorder_curriculum_api(self):
        """Kiểm tra API kéo thả sắp xếp thứ tự Chương & Bài học"""
        reorder_url = reverse('course_curriculum_reorder', args=[self.course.key])

        # 1. Chưa đăng nhập -> 302/403
        resp = self.client.post(
            reorder_url,
            data=json.dumps({'action': 'reorder_chapters', 'chapter_ids': []}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, (302, 403))

        # 2. Đăng nhập là học viên (không có quyền edit) -> 403
        self.client.login(username='student1', password=self.password)
        resp = self.client.post(
            reorder_url,
            data=json.dumps({'action': 'reorder_chapters', 'chapter_ids': []}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)

        # 3. Đăng nhập là Giảng viên
        self.client.login(username='instructor1', password=self.password)

        # Tạo thêm chương 2 và bài học 2
        chapter2 = Chapter.objects.create(course=self.course, title='Chương 2', order_index=1)
        lesson2 = Lesson.objects.create(chapter=self.chapter, title='Bài học 2', order_index=1)

        # Sắp xếp lại chương: đưa chapter2 lên đầu (order 0), chapter 1 xuống sau (order 1)
        resp = self.client.post(
            reorder_url,
            data=json.dumps({'action': 'reorder_chapters', 'chapter_ids': [chapter2.id, self.chapter.id]}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        chapter2.refresh_from_db()
        self.chapter.refresh_from_db()
        self.assertEqual(chapter2.order_index, 0)
        self.assertEqual(self.chapter.order_index, 1)

        # Sắp xếp và di chuyển bài học: đưa lesson2 sang chapter2 với order 0
        resp = self.client.post(
            reorder_url,
            data=json.dumps({
                'action': 'reorder_lessons',
                'lessons': [
                    {'id': lesson2.id, 'chapter_id': chapter2.id, 'order_index': 0},
                    {'id': self.lesson1.id, 'chapter_id': self.chapter.id, 'order_index': 0},
                ],
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        lesson2.refresh_from_db()
        self.lesson1.refresh_from_db()
        self.assertEqual(lesson2.chapter_id, chapter2.id)
        self.assertEqual(lesson2.order_index, 0)
        self.assertEqual(self.lesson1.order_index, 0)
