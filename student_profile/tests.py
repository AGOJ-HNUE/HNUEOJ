from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from .models import Semester, Subject, StudentGrade
from .views import calculate_academic_summary

User = get_user_model()


class StudentAcademicProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='teststudent', password='testpassword123')
        self.client = Client()
        self.client.login(username='teststudent', password='testpassword123')

        self.sem1 = Semester.objects.create(id='2023_2024_HK1', name='Học kỳ 1', academic_year='2023-2024', order=1)
        self.sem2 = Semester.objects.create(id='2023_2024_HK2', name='Học kỳ 2', academic_year='2023-2024', order=2)

        self.subj1 = Subject.objects.create(code='COMP101', name='Lập trình C++', credits=3)
        self.subj2 = Subject.objects.create(code='MATH101', name='Giải tích 1', credits=3)
        self.subj3 = Subject.objects.create(code='PHYS101', name='Vật lý đại cương', credits=2)

    def test_gpa_cpa_calculation(self):
        # A = 4.0 (3 TC) -> 12
        # B+ = 3.5 (3 TC) -> 10.5
        # F = 0.0 (2 TC) -> 0.0
        # Total points = 22.5 / 8 credits = 2.8125 -> 2.81
        # Passed credits = 3 + 3 = 6 (F ignored)
        g1 = StudentGrade.objects.create(user=self.user, semester=self.sem1, subject=self.subj1, letter_grade='A')
        g2 = StudentGrade.objects.create(user=self.user, semester=self.sem1, subject=self.subj2, letter_grade='B+')
        g3 = StudentGrade.objects.create(user=self.user, semester=self.sem2, subject=self.subj3, letter_grade='F')

        all_grades = StudentGrade.objects.filter(user=self.user)
        cpa, passed_credits, total_credits = calculate_academic_summary(all_grades)

        self.assertEqual(cpa, 2.81)
        self.assertEqual(passed_credits, 6)
        self.assertEqual(total_credits, 8)

    def test_api_save_and_get_grades(self):
        # Test API save grade
        payload = {
            'semester_id': '2023_2024_HK1',
            'subject_code': 'COMP201',
            'subject_name': 'Cấu trúc dữ liệu và giải thuật',
            'credits': 4,
            'letter_grade': 'A'
        }
        res = self.client.post('/student-profile/api/grades/save/', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)

        # Test API get grades
        res_get = self.client.get('/student-profile/api/grades/?semester_id=2023_2024_HK1')
        self.assertEqual(res_get.status_code, 200)
        data = res_get.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['cpa'], 4.0)
        self.assertEqual(data['passed_credits'], 4)
        self.assertEqual(len(data['grades']), 1)
        self.assertEqual(data['grades'][0]['subject_code'], 'COMP201')
