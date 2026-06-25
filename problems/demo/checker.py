import json
import math
from dmoj.result import CheckerResult

def wa(feedback):
    return CheckerResult(False, 0, feedback)

def parse_multiple_json(text):
    """Bóc tách nhiều object JSON từ một chuỗi (xử lý việc in trên 1 dòng hoặc nhiều dòng)"""
    decoder = json.JSONDecoder()
    text = text.lstrip()
    results = []
    
    while text:
        try:
            obj, index = decoder.raw_decode(text)
            results.append(obj)
            text = text[index:].lstrip()
        except json.JSONDecodeError:
            break
            
    return results

def compare_part_a(user_dict, exp_dict, tol=1e-5):
    """Kiểm tra câu a: object chứa mảng số tiền"""
    if not isinstance(user_dict, dict) or not isinstance(exp_dict, dict):
        return False
    if user_dict.keys() != exp_dict.keys():
        return False
        
    for key in exp_dict:
        if not isinstance(user_dict[key], list) or len(user_dict[key]) != len(exp_dict[key]):
            return False
        # Chống trôi sai số nếu input có số thực
        for u_val, e_val in zip(user_dict[key], exp_dict[key]):
            try:
                if not math.isclose(float(u_val), float(e_val), abs_tol=tol):
                    return False
            except (ValueError, TypeError):
                return False
    return True

def compare_float_dicts(user_dict, exp_dict, tol=1e-5):
    """Kiểm tra câu b và c: object chứa số thực (tổng/trung bình)"""
    if not isinstance(user_dict, dict) or not isinstance(exp_dict, dict):
        return False
    if user_dict.keys() != exp_dict.keys():
        return False
    
    for key in exp_dict:
        try:
            val_user = float(user_dict[key])
            val_exp = float(exp_dict[key])
            if not math.isclose(val_user, val_exp, abs_tol=tol):
                return False
        except (ValueError, TypeError):
            return False
    return True

def compare_part_d(user_ans, exp_ans):
    """Kiểm tra câu d: mảng danh mục chi nhiều nhất (không quan tâm thứ tự)"""
    if isinstance(user_ans, str): user_ans = [user_ans]
    if isinstance(exp_ans, str): exp_ans = [exp_ans]
    
    if not isinstance(user_ans, list) or not isinstance(exp_ans, list):
        return False
        
    return set(user_ans) == set(exp_ans)

def check(process_output, judge_output, judge_input, **kwargs):
    # Decode bytes sang string (DMOJ truyền dữ liệu dạng bytes)
    try:
        user_str = process_output.decode('utf-8')
        exp_str = judge_output.decode('utf-8')
    except UnicodeDecodeError:
        return wa('Wrong output format: Lỗi encoding.')

    # Parse JSON
    user_jsons = parse_multiple_json(user_str)
    exp_jsons = parse_multiple_json(exp_str)

    # Kiểm tra số lượng object
    if len(user_jsons) != 4:
        return wa(f'Presentation Error: Yêu cầu 4 kết quả JSON, nhận được {len(user_jsons)}.')
    
    if len(exp_jsons) != 4:
        return wa('Judge Error: File đáp án (Answer) bị lỗi cấu trúc.')

    # a. Hàm nhomTheoLoai
    if not compare_part_a(user_jsons[0], exp_jsons[0]):
        return wa('Wrong Answer: Kết quả hàm nhomTheoLoai (câu a) sai.')

    # b. Hàm tongTheoLoai
    if not compare_float_dicts(user_jsons[1], exp_jsons[1]):
        return wa('Wrong Answer: Kết quả hàm tongTheoLoai (câu b) sai.')

    # c. Hàm trungBinhTheoLoai
    if not compare_float_dicts(user_jsons[2], exp_jsons[2], tol=0.015):
        return wa('Wrong Answer: Kết quả hàm trungBinhTheoLoai (câu c) sai.')

    # d. Hàm loaiChiNhieu
    if not compare_part_d(user_jsons[3], exp_jsons[3]):
        return wa('Wrong Answer: Kết quả hàm loaiChiNhieu (câu d) sai.')

    # Trả về True tương đương với Accepted (AC) và nhận 100% điểm của test case đó
    return True