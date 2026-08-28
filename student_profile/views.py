import json
import uuid
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import Semester, Subject, StudentGrade

# Thang điểm chuẩn của Trường Đại học Sư phạm Hà Nội (HNUE)
HNUE_GRADE_SCALE = {
    "A": 4.0,
    "B+": 3.5,
    "B": 3.0,
    "C+": 2.5,
    "C": 2.0,
    "D+": 1.5,
    "D": 1.0,
    "F": 0.0,
}


def get_hnue_point(letter_grade):
    if not letter_grade or letter_grade not in HNUE_GRADE_SCALE:
        return None
    return HNUE_GRADE_SCALE[letter_grade]


def compute_smart_recommendations(user_grades, target_cpa=3.60):
    # 1. Bản đồ ưu tiên qua màng lọc ảo / quy chế đăng ký cải thiện
    # F: 1 (Bắt buộc học lại), D: 2, D+: 3, C: 4, C+: 5, B: 6, B+: 7
    RISK_PRIORITY = {
        'F': 1,
        'D': 2,
        'D+': 3,
        'C': 4,
        'C+': 5,
        'B': 6,
        'B+': 7,
    }

    total_points = 0.0
    total_credits = 0
    passed_credits = 0

    candidates = []

    for g in user_grades:
        eff_letter = g.effective_letter_grade
        point = get_hnue_point(eff_letter)

        if point is not None:
            credits = g.subject.credits
            total_points += point * credits
            total_credits += credits
            if eff_letter != 'F':
                passed_credits += credits

            if point < 4.0 and eff_letter in RISK_PRIORITY:
                gain_a = (4.0 - point) * credits
                gain_b_plus = (3.5 - point) * credits if point < 3.5 else 0.0
                priority_val = RISK_PRIORITY[eff_letter]

                candidates.append({
                    'grade_id': g.id,
                    'subject_name': g.subject.name,
                    'subject_code': g.subject.code,
                    'semester_name': g.semester.name,
                    'credits': credits,
                    'difficulty': getattr(g.subject, 'difficulty', 5),
                    'current_letter': eff_letter,
                    'current_point': point,
                    'gain_b_plus': round(gain_b_plus, 2),
                    'gain_a': round(gain_a, 2),
                    'potential_gain_to_A': round(gain_a, 2),
                    'priority_level': priority_val,
                })

    current_cpa = round(total_points / total_credits, 2) if total_credits > 0 else 0.00

    # Sắp xếp Knapsack: 
    # 1. Nhóm lọc ảo (priority_level ASC: F -> D -> D+ -> C -> C+ -> B -> B+)
    # 2. Đòn bẩy điểm số (-gain_a DESC)
    # 3. Độ khó môn học (difficulty ASC: 1 -> 10, môn dễ hơn ưu tiên trước)
    # 4. Số tín chỉ (-credits DESC)
    # 5. Thứ tự từ điển tên môn học (subject_name.lower() ASC)
    candidates.sort(key=lambda x: (
        x['priority_level'],
        -x['gain_a'],
        x.get('difficulty', 5),
        -x['credits'],
        x['subject_name'].lower()
    ))

    simulated_points = total_points
    simulated_cpa = current_cpa
    target_plan = []
    recommended_map = {}

    if target_cpa > current_cpa and total_credits > 0:
        for c in candidates:
            # Kiểm tra xem nâng lên B+ đã đủ chạm target CPA chưa
            if c['gain_b_plus'] > 0 and (round((simulated_points + c['gain_b_plus']) / total_credits, 2) >= target_cpa):
                simulated_points += c['gain_b_plus']
                simulated_cpa = round(simulated_points / total_credits, 2)
                suggested_target = 'B+'
                badge_text = '🎯 Cải thiện ➔ B+'
            else:
                simulated_points += c['gain_a']
                simulated_cpa = round(simulated_points / total_credits, 2)
                suggested_target = 'A'
                badge_text = '🎯 Cải thiện ➔ A'

            target_plan.append({
                'grade_id': c['grade_id'],
                'subject_name': c['subject_name'],
                'credits': c['credits'],
                'from_letter': c['current_letter'],
                'to_letter': suggested_target,
                'badge_text': badge_text,
                'projected_cpa': simulated_cpa
            })
            recommended_map[str(c['grade_id'])] = {
                'target_letter': suggested_target,
                'badge_text': badge_text
            }
            if simulated_cpa >= target_cpa:
                break

    return {
        'current_cpa': current_cpa,
        'passed_credits': passed_credits,
        'total_credits': total_credits,
        'recommendations': candidates,
        'target_plan': target_plan,
        'recommended_map': recommended_map,
        'needed_subjects_count': len(target_plan) if simulated_cpa >= target_cpa else 0,
        'target_achievable': simulated_cpa >= target_cpa
    }


@login_required
def profile_dashboard(request):
    return render(request, 'student_profile/index.html', {
        'title': 'Hồ sơ học tập HNUE | Quản lý GPA & CPA Tín chỉ',
        'student_user': request.user,
    })


@login_required
@require_http_methods(["GET"])
def api_get_full_profile(request):
    target_cpa = float(request.GET.get('target_cpa', 3.20))

    semesters = Semester.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    ).order_by('academic_year', 'order', 'created_at')

    user_grades = StudentGrade.objects.filter(user=request.user).select_related('subject', 'semester')
    grades_by_sem = {}
    for g in user_grades:
        grades_by_sem.setdefault(g.semester_id, []).append(g)

    semesters_data = []
    chart_labels = []
    chart_gpa_series = []
    chart_cpa_series = []

    cumulative_points = 0.0
    cumulative_credits = 0
    cumulative_passed_credits = 0

    for sem in semesters:
        sem_grades = grades_by_sem.get(sem.id, [])
        subjects_list = []

        sem_points = 0.0
        sem_credits = 0
        sem_passed_credits = 0

        for g in sem_grades:
            eff_letter = g.effective_letter_grade
            point = get_hnue_point(eff_letter)

            if point is not None:
                sem_points += point * g.subject.credits
                sem_credits += g.subject.credits
                if eff_letter != 'F':
                    sem_passed_credits += g.subject.credits

            subjects_list.append({
                'id': g.id,
                'subject_code': g.subject.code,
                'subject_name': g.subject.name,
                'credits': g.subject.credits,
                'difficulty': g.subject.difficulty,
                'letter_grade': g.letter_grade or '',
                'improvement_grade': g.improvement_grade or '',
                'target_grade': g.target_grade or '',
                'score_4': point if point is not None else 0.0,
                'is_passed': eff_letter != 'F' if eff_letter else False,
            })

        sem_gpa = round(sem_points / sem_credits, 2) if sem_credits > 0 else 0.00

        cumulative_points += sem_points
        cumulative_credits += sem_credits
        cumulative_passed_credits += sem_passed_credits

        sem_cpa = round(cumulative_points / cumulative_credits, 2) if cumulative_credits > 0 else 0.00

        semesters_data.append({
            'id': sem.id,
            'name': sem.name,
            'academic_year': sem.academic_year,
            'order': sem.order,
            'subjects': subjects_list,
            'summary': {
                'semester_gpa': sem_gpa,
                'cumulative_cpa': sem_cpa,
                'semester_passed_credits': sem_passed_credits,
                'cumulative_passed_credits': cumulative_passed_credits,
                'semester_total_credits': sem_credits,
                'cumulative_total_credits': cumulative_credits,
            }
        })

        if sem_credits > 0:
            chart_labels.append(sem.name)
            chart_gpa_series.append(sem_gpa)
            chart_cpa_series.append(sem_cpa)

    total_cpa = round(cumulative_points / cumulative_credits, 2) if cumulative_credits > 0 else 0.00
    smart_advisor = compute_smart_recommendations(user_grades, target_cpa)

    # Danh mục toàn bộ học phần trong CTĐT Sư phạm Tin học phục vụ instant search
    curriculum_subjects = list(
        Subject.objects.all().values('code', 'name', 'credits', 'difficulty').order_by('code')
    )

    return JsonResponse({
        'status': 'success',
        'cpa': total_cpa,
        'passed_credits': cumulative_passed_credits,
        'total_credits': cumulative_credits,
        'semesters': semesters_data,
        'curriculum_subjects': curriculum_subjects,
        'chart': {
            'labels': chart_labels,
            'gpa_series': chart_gpa_series,
            'cpa_series': chart_cpa_series,
        },
        'smart_advisor': smart_advisor
    })


@login_required
@require_http_methods(["GET"])
def api_search_curriculum_subjects(request):
    """Tìm kiếm học phần trong chương trình đào tạo theo mã hoặc tên"""
    q = request.GET.get('q', '').strip()
    qs = Subject.objects.all()
    if q:
        qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
    results = list(qs.values('code', 'name', 'credits', 'difficulty')[:30])
    return JsonResponse({'status': 'success', 'results': results})


@login_required
@require_http_methods(["POST"])
def api_update_grade_value(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        grade_id = data.get('grade_id')
        field = data.get('field')
        value = data.get('value')

        grade = StudentGrade.objects.get(id=grade_id, user=request.user)

        if field == 'letter_grade':
            grade.letter_grade = value if value else None
        elif field == 'improvement_grade':
            grade.improvement_grade = value if value else None
        elif field == 'target_grade':
            grade.target_grade = value if value else None
        else:
            return HttpResponseBadRequest(JsonResponse({'status': 'error', 'message': 'Trường không hợp lệ'}))

        grade.save(update_fields=[field])
        return JsonResponse({'status': 'success', 'message': 'Đã cập nhật điểm!'})
    except StudentGrade.DoesNotExist:
        return HttpResponseNotFound(JsonResponse({'status': 'error', 'message': 'Không tìm thấy môn học'}))
    except Exception as e:
        return HttpResponseBadRequest(JsonResponse({'status': 'error', 'message': str(e)}))


@login_required
@require_http_methods(["POST"])
def api_save_subject(request):
    """Thêm môn học mới hoặc sửa điểm môn học từ danh mục CTĐT chính thức"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        grade_id = data.get('grade_id')
        semester_id = data.get('semester_id')
        user_code = str(data.get('subject_code', '')).strip()
        subject_name = str(data.get('subject_name', '')).strip()
        letter_grade = data.get('letter_grade', '') or None
        improvement_grade = data.get('improvement_grade', '') or None
        target_grade = data.get('target_grade', '') or None

        if not semester_id:
            return HttpResponseBadRequest(JsonResponse({'status': 'error', 'message': 'Vui lòng chọn học kỳ!'}))

        semester = Semester.objects.get(id=semester_id)

        with transaction.atomic():
            if grade_id:
                # Sửa điểm môn học hiện có
                grade = StudentGrade.objects.select_related('subject').get(id=grade_id, user=request.user)
                subject = grade.subject
                
                # Nếu người dùng đổi sang môn khác từ danh mục CTĐT
                if user_code and user_code != subject.code:
                    official_sub = Subject.objects.filter(code=user_code).first()
                    if official_sub:
                        subject = official_sub
                        grade.subject = subject
                elif subject_name and subject_name != subject.name:
                    official_sub = Subject.objects.filter(name__iexact=subject_name).first()
                    if official_sub:
                        subject = official_sub
                        grade.subject = subject

                grade.letter_grade = letter_grade
                grade.improvement_grade = improvement_grade
                grade.target_grade = target_grade
                grade.save()
            else:
                # Tìm môn học chính thức trong danh mục CTĐT
                subject = None
                if user_code:
                    subject = Subject.objects.filter(code=user_code).first()
                if not subject and subject_name:
                    subject = Subject.objects.filter(name__iexact=subject_name).first()
                
                # Nếu không khớp chính xác, thử tìm theo mã hoặc tên
                if not subject and (user_code or subject_name):
                    search_term = user_code or subject_name
                    subject = Subject.objects.filter(Q(code__iexact=search_term) | Q(name__iexact=search_term)).first()

                if not subject:
                    return HttpResponseBadRequest(JsonResponse({
                        'status': 'error',
                        'message': 'Vui lòng chọn học phần có trong chương trình đào tạo Sư phạm Tin học!'
                    }))

                grade, _ = StudentGrade.objects.update_or_create(
                    user=request.user,
                    semester=semester,
                    subject=subject,
                    defaults={
                        'letter_grade': letter_grade,
                        'improvement_grade': improvement_grade,
                        'target_grade': target_grade
                    }
                )

        return JsonResponse({'status': 'success', 'message': 'Đã lưu môn học thành công!', 'grade_id': grade.id})
    except Semester.DoesNotExist:
        return HttpResponseNotFound(JsonResponse({'status': 'error', 'message': 'Không tìm thấy học kỳ!'}))
    except Exception as e:
        return HttpResponseBadRequest(JsonResponse({'status': 'error', 'message': str(e)}))


@login_required
@require_http_methods(["POST"])
def api_add_semester(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        name = str(data.get('name', '')).strip()
        academic_year = str(data.get('academic_year', '2025-2026')).strip()
        order = int(data.get('order', 1))

        if not name:
            return HttpResponseBadRequest(JsonResponse({'status': 'error', 'message': 'Vui lòng nhập tên học kỳ!'}))

        sem_id = f"sem_{request.user.id}_{uuid.uuid4().hex[:8]}"
        semester = Semester.objects.create(
            id=sem_id,
            name=name,
            academic_year=academic_year,
            order=order,
            user=request.user
        )
        return JsonResponse({'status': 'success', 'message': 'Đã thêm học kỳ mới!', 'semester_id': semester.id})
    except Exception as e:
        return HttpResponseBadRequest(JsonResponse({'status': 'error', 'message': str(e)}))


@login_required
@require_http_methods(["POST"])
def api_edit_semester(request, semester_id):
    try:
        data = json.loads(request.body.decode('utf-8'))
        name = str(data.get('name', '')).strip()
        if not name:
            return HttpResponseBadRequest(JsonResponse({'status': 'error', 'message': 'Tên học kỳ không được để trống'}))

        semester = Semester.objects.get(id=semester_id)
        semester.name = name
        if 'academic_year' in data:
            semester.academic_year = data['academic_year']
        semester.save()
        return JsonResponse({'status': 'success', 'message': 'Đã cập nhật học kỳ!'})
    except Semester.DoesNotExist:
        return HttpResponseNotFound(JsonResponse({'status': 'error', 'message': 'Không tìm thấy học kỳ'}))


@login_required
@require_http_methods(["DELETE", "POST"])
def api_delete_semester(request, semester_id):
    try:
        StudentGrade.objects.filter(semester_id=semester_id, user=request.user).delete()
        Semester.objects.filter(id=semester_id, user=request.user).delete()
        return JsonResponse({'status': 'success', 'message': 'Đã xóa học kỳ!'})
    except Exception as e:
        return HttpResponseBadRequest(JsonResponse({'status': 'error', 'message': str(e)}))


@login_required
@require_http_methods(["DELETE", "POST"])
def api_delete_grade(request, grade_id):
    try:
        StudentGrade.objects.filter(id=grade_id, user=request.user).delete()
        return JsonResponse({'status': 'success', 'message': 'Đã xóa môn học!'})
    except Exception as e:
        return HttpResponseBadRequest(JsonResponse({'status': 'error', 'message': str(e)}))


@login_required
@require_http_methods(["POST"])
def api_reset_profile(request):
    try:
        StudentGrade.objects.filter(user=request.user).delete()
        return JsonResponse({'status': 'success', 'message': 'Đã reset toàn bộ hồ sơ điểm!'})
    except Exception as e:
        return HttpResponseBadRequest(JsonResponse({'status': 'error', 'message': str(e)}))
