import re
from html.parser import HTMLParser
from dmoj.result import CheckerResult

# --- BỘ PHÂN TÍCH CẤU TRÚC HTML (Chống in lách luật ra ngoài bảng) ---
class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_tr = False
        self.in_td = False
        self.current_cell_data = []
        self.current_row_data = []
        self.table_data = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
        elif tag == 'tr' and self.in_table:
            self.in_tr = True
            self.current_row_data = []
        elif tag in ('td', 'th') and self.in_tr:
            self.in_td = True
            self.current_cell_data = []

    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
        elif tag == 'tr' and self.in_table:
            self.in_tr = False
            # Chỉ lưu các hàng có nội dung
            if self.current_row_data:
                self.table_data.append(self.current_row_data)
        elif tag in ('td', 'th') and self.in_tr:
            self.in_td = False
            # Gộp text (bỏ qua mọi thẻ HTML con lồng bên trong như <b>, <span>)
            cell_text = "".join(self.current_cell_data).strip()
            # Xóa các khoảng trắng/xuống dòng thừa thãi trong code HTML của sinh viên
            cell_text = re.sub(r'\s+', ' ', cell_text)
            self.current_row_data.append(cell_text)

    def handle_data(self, data):
        # CHỈ thu thập text nếu nó nằm hợp lệ bên trong thẻ <td> hoặc <th>
        if self.in_td:
            self.current_cell_data.append(data)


# --- HÀM CHẤM ĐIỂM CHÍNH ---
def check(process_output, judge_output, **kwargs):
    # 1. Tiền xử lý Output và Source code
    if isinstance(process_output, bytes):
        process_output = process_output.decode('utf-8', errors='ignore')
        
    submission_source = kwargs.get('submission_source', b'')
    if isinstance(submission_source, bytes):
        submission_source = submission_source.decode('utf-8', errors='ignore')

    # 2. Xây dựng cây dữ liệu bằng HTML Parser
    parser = TableParser()
    try:
        parser.feed(process_output)
    except Exception:
        pass # Bỏ qua lỗi nếu sinh viên viết HTML quá sai chuẩn (sẽ bị 0 điểm bảng)

    extracted_rows = parser.table_data

    # 3. Dữ liệu đối chiếu chuẩn
    expected_data = [
        {
            "rut_gon": "Huong dan lap trinh PHP cho nguoi moi bat dau hoc ...",
            "dem_tu": "14",
            "slug": "huong-dan-lap-trinh-php-cho-nguoi-moi-bat-dau-hoc-lap-trinh-web"
        },
        {
            "rut_gon": "Top 10 thu vien JavaScript pho bien nhat nam 2025",
            "dem_tu": "10",
            "slug": "top-10-thu-vien-javascript-pho-bien-nhat-nam-2025"
        },
        {
            "rut_gon": "MySQL vs PostgreSQL",
            "dem_tu": "3",
            "slug": "mysql-vs-postgresql"
        },
        {
            "rut_gon": "Cach toi uu hoa toc do website cua ban voi nhung m...",
            "dem_tu": "14",
            "slug": "cach-toi-uu-hoa-toc-do-website-cua-ban-voi-nhung-meo-don-gian"
        }
    ]

    # Khởi tạo điểm
    score_table = 0
    score_rut_gon = 0
    score_dem_tu = 0
    score_slug = 0

    # 4. Chấm điểm Cấu trúc Bảng
    # Bảng hợp lệ phải có ít nhất 5 hàng (1 hàng tiêu đề + 4 hàng dữ liệu)
    if len(extracted_rows) >= 5:
        score_table = 2
    elif len(extracted_rows) > 0:
        score_table = 1 # Cho 1 điểm an ủi nếu có vẽ bảng nhưng thiếu dữ liệu

    # Chỉ giữ lại các hàng có ít nhất 5 cột (để đảm bảo không bị lỗi index out of bounds)
    valid_data_rows = [row for row in extracted_rows if len(row) >= 5]

    # 5. Chấm điểm Dữ liệu (Duyệt tuần tự để ép buộc đúng thứ tự bài viết và đúng cột)
    correct_rut_gon = 0
    correct_dem_tu = 0
    correct_slug = 0
    
    expected_index = 0
    for row in valid_data_rows:
        if expected_index >= 4:
            break # Đã chấm xong 4 bài viết yêu cầu
            
        exp = expected_data[expected_index]
        
        # Ép cứng vị trí: Cột 3 (index 2) = Rút gọn | Cột 4 (index 3) = Đếm từ | Cột 5 (index 4) = Slug
        match_rg = (row[2] == exp["rut_gon"])
        match_dt = (row[3] == exp["dem_tu"])
        match_sl = (row[4] == exp["slug"])
        
        # Nếu hàng này có bất kỳ cột nào khớp với dữ liệu kỳ vọng, ta xác định đây là hàng dữ liệu
        # (Giúp tự động bỏ qua các hàng header chứa chữ "STT", "Tiêu đề"...)
        if match_rg or match_dt or match_sl:
            if match_rg: correct_rut_gon += 1
            if match_dt: correct_dem_tu += 1
            if match_sl: correct_slug += 1
            
            # Chuyển sang kiểm tra bài viết tiếp theo ở hàng dưới
            expected_index += 1

    # Tính điểm thành phần (Đúng cả 4 mới được full điểm của cột đó)
    if correct_rut_gon == 4: score_rut_gon = 3
    if correct_dem_tu == 4: score_dem_tu = 2
    if correct_slug == 4: score_slug = 3

    # 6. Kiểm tra Source Code chặt chẽ bằng Regex (Chống viết thẳng, bắt buộc định nghĩa hàm)
    # \s+ đảm bảo bắt đúng có khoảng trắng; \b đảm bảo là ranh giới từ (không bị dính chữ)
    if not re.search(r'function\s+rut_gon_chuoi\b', submission_source, re.IGNORECASE):
        score_rut_gon = 0
    if not re.search(r'function\s+dem_tu\b', submission_source, re.IGNORECASE):
        score_dem_tu = 0
    if not re.search(r'function\s+tao_slug\b', submission_source, re.IGNORECASE):
        score_slug = 0

    # 7. Trả kết quả
    total_score = score_table + score_rut_gon + score_dem_tu + score_slug
    
    feedback = (f"Bảng HTML: {score_table}/2 | "
                f"Hàm rut_gon_chuoi: {score_rut_gon}/3 | "
                f"Hàm dem_tu: {score_dem_tu}/2 | "
                f"Hàm tao_slug: {score_slug}/3")

    return CheckerResult(total_score == 10, total_score, feedback)