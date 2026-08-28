# BÁO CÁO KỸ THUẬT: THUẬT TOÁN ĐỀ XUẤT MÔN HỌC CẢI THIỆN TỐI ƯU (SMART CPA ADVISOR ALGORITHM)
**Hệ thống:** HNUE OJ - Phân hệ Hồ sơ Học tập & Quản lý Tín chỉ Ngành Sư Phạm Tin Học  
**Phiên bản thuật toán:** 3.0 (Multi-Tier Greedy Knapsack with Registration Risk Filter & Course Difficulty Weights)

---

## 1. ĐẶT VẤN ĐỀ VÀ BỐI CẢNH THỰC TIỄN

Trong đào tạo theo hệ thống tín chỉ tại Trường Đại học Sư phạm Hà Nội (thang điểm 4.0), điểm trung bình chung tích lũy (CPA) là tiêu chí cốt lõi quyết định xếp loại bằng tốt nghiệp:
- **Xuất sắc:** $\text{CPA} \ge 3.60$
- **Giỏi:** $\text{CPA} \ge 3.20$
- **Khá:** $\text{CPA} \ge 2.50$
- **Trung bình:** $\text{CPA} \ge 2.00$

Khi sinh viên có nguyện vọng nâng hạng tốt nghiệp (ví dụ từ Khá lên Giỏi, hoặc từ Giỏi lên Xuất sắc), việc chọn môn nào để học cải thiện thường gặp các rào cản lớn:
1. **Số lượng môn cần học lại:** Sinh viên không thể học lại quá nhiều môn do giới hạn số tín chỉ tối đa trong một học kỳ và chi phí thời gian/học phí.
2. **Rào cản "Bộ lọc ảo" đăng ký tín chỉ:** Hệ thống ĐKTC của nhà trường ưu tiên xếp lịch cho sinh viên học lần đầu. Sinh viên cải thiện các môn điểm trung bình (C+, B, B+) có nguy cơ bị hủy lớp nếu quá tải phòng học.
3. **Độ khó môn học không đồng đều:** Các môn đại cương hoặc lý thuyết nặng đòi hỏi nhiều nỗ lực hơn các môn cơ sở/chuyên ngành thực hành.

**Mục tiêu của Thuật toán:** Tìm ra tập hợp tối thiểu các môn học cần cải thiện sao cho đạt được $\text{CPA}_{\text{target}}$ với tổng số tín chỉ phải học lại ít nhất, rủi ro ĐKTC thấp nhất và ưu tiên các môn học có độ khó thấp hơn.

---

## 2. MÔ HÌNH HÓA TOÁN HỌC (MATHEMATICAL FORMULATION)

### 2.1. Không gian trạng thái và Ký hiệu

Giả sử sinh viên đã tích lũy $m$ môn học với danh sách bộ ba $(TC_i, g_i, d_i)_{i=1}^m$:
- $TC_i \in \{1, 2, 3, 4, 5, 6\}$: Số tín chỉ của môn $i$.
- $g_i \in \{0.0, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0\}$: Điểm chữ hiện tại quy đổi sang thang 4.0 theo chuẩn HNUE:
  $$\{A: 4.0, B+: 3.5, B: 3.0, C+: 2.5, C: 2.0, D+: 1.5, D: 1.0, F: 0.0\}$$
- $d_i \in [1, 10]$: Trọng số độ khó của môn học trong chương trình đào tạo (1 là dễ nhất, 10 là khó nhất). Môn chưa cấu hình mặc định là 10.

Tổng số tín chỉ tích lũy hiện tại:
$$N = \sum_{i=1}^m TC_i$$

Điểm tổng tích lũy hiện tại và CPA hiện tại:
$$\text{Points}_{\text{current}} = \sum_{i=1}^m (g_i \times TC_i), \quad \text{CPA}_{\text{current}} = \frac{\text{Points}_{\text{current}}}{N}$$

### 2.2. Điểm thiếu hụt cần bù đắp ($\text{Points}_{\text{needed}}$)

Để đạt mục tiêu $\text{CPA}_{\text{target}}$, tổng điểm tích lũy cần đạt tối thiểu là:
$$\text{Points}_{\text{target}} = \text{CPA}_{\text{target}} \times N$$

Lượng điểm chất lượng tổng cần bù đắp là:
$$\Delta_{\text{Total}} = \text{Points}_{\text{target}} - \text{Points}_{\text{current}} = (\text{CPA}_{\text{target}} - \text{CPA}_{\text{current}}) \times N$$

Nếu $\Delta_{\text{Total}} \le 0$, sinh viên đã đạt mục tiêu $\rightarrow$ Không cần học cải thiện.

### 2.3. Đòn bẩy tăng điểm của từng môn ($\Delta_i$)

Với mỗi môn $i$ có điểm $g_i < 4.0$:
- Đòn bẩy tối đa khi cải thiện lên điểm **A (4.0)**:
  $$\Delta_{i, A} = (4.0 - g_i) \times TC_i$$
- Đòn bẩy khi cải thiện lên điểm **B+ (3.5)**:
  $$\Delta_{i, B+} = (3.5 - g_i) \times TC_i \quad (\text{áp dụng khi } g_i < 3.5)$$

---

## 3. THUẬT TOÁN PHÂN LỚP VÀ BỘ SO SÁNH ĐA TẦNG (5-TIER COMPARATOR)

Bài toán tương đương dạng **Knapsack Problem (Bài toán cái túi)** kết hợp xếp hạng ưu tiên có điều kiện rủi ro. Thuật toán tiến hành theo 4 giai đoạn:

```
+-------------------------------------------------------------------------+
| GIAI ĐOẠN 1: Lọc ứng viên (Candidate Filtering)                         |
| Loại bỏ các môn đã đạt điểm A (4.0)                                     |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| GIAI ĐOẠN 2: Phân lớp rủi ro ĐKTC (Registration Risk Stratification)    |
| - Nhóm 1 (Level 1): Điểm F (0.0) -> Bắt buộc học lại (Rủi ro = 0)       |
| - Nhóm 2 (Level 2): Điểm D, D+, C (1.0 - 2.0) -> Điểm thấp (Rủi ro thấp)|
| - Nhóm 3 (Level 3): Điểm C+, B, B+ (2.5 - 3.5) -> Điểm khá (Rủi ro cao) |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| GIAI ĐOẠN 3: Sắp xếp theo Bộ so sánh 5 tiêu chí (5-Tier Comparator)     |
| K1: Nhóm ưu tiên rủi ro (Level 1 -> Level 2 -> Level 3)                 |
| K2: Đòn bẩy tăng điểm Δ_i,A giảm dần                                    |
| K3: Độ khó môn học d_i tăng dần (1 -> 10)                               |
| K4: Số tín chỉ TC_i giảm dần                                            |
| K5: Thứ tự từ điển tiếng Việt (Alphabetical Determinism)                |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| GIAI ĐOẠN 4: Lựa chọn Tham lam & Tối ưu mức điểm (Greedy Optimization)  |
| Duyệt từng môn: Thử nâng lên B+ trước, nếu chưa đủ thì nâng lên A       |
| Dừng ngay khi: Tổng điểm bù đắp >= Δ_Total                              |
+-------------------------------------------------------------------------+
```

### Chi tiết Bộ so sánh 5 tiêu chí ($K_1 \rightarrow K_5$):

$$\text{SoSanh}(A, B) = \begin{cases}
K_1: \text{Level}_A - \text{Level}_B & \text{Nếu khác nhóm rủi ro ĐKTC (Level 1: F, Level 2: D/C, Level 3: C+/B)} \\
K_2: -(\Delta_{A, A} - \Delta_{B, A}) & \text{Nếu đòn bẩy tăng điểm } \Delta_{i,A} \text{ khác nhau (ưu tiên đòn bẩy lớn)} \\
K_3: d_A - d_B & \text{Nếu cùng đòn bẩy, ưu tiên môn dễ hơn (độ khó nhỏ hơn)} \\
K_4: -(TC_A - TC_B) & \text{Nếu cùng độ khó, ưu tiên môn nhiều tín chỉ hơn} \\
K_5: \text{LocaleCompare}(Name_A, Name_B) & \text{Thứ tự từ điển tiếng Việt (đảm bảo tính tất định)}
\end{cases}$$

### Tối ưu hóa mức điểm gợi ý ($B+$ vs $A$):
Để giảm áp lực học tập cho sinh viên, với mỗi môn được chọn:
- Giả sử lượng điểm còn thiếu tại bước hiện tại là $R$ (ban đầu $R = \Delta_{\text{Total}}$).
- Nếu $g_i < 3.5$ và đòn bẩy khi lên $B+$ đã đủ bù đắp phần còn lại ($\Delta_{i, B+} \ge R$):
  $$\rightarrow \text{Gợi ý nhãn: } \mathbf{[🎯\text{ Cải thiện } \rightarrow B+]}$$
- Ngược lại (nếu cần đòn bẩy tối đa hoặc môn có điểm gốc $\ge 3.0$):
  $$\rightarrow \text{Gợi ý nhãn: } \mathbf{[🎯\text{ Cải thiện } \rightarrow A]}$$

---

## 4. VÍ DỤ MINH HỌA SỐ LIỆU THỰC TẾ CHI TIẾT

### 4.1. Dữ liệu đầu vào của sinh viên
- **Sinh viên:** Nguyễn Văn A (K73 - Sư phạm Tin học)
- **Tổng số tín chỉ đã học:** $N = 45\text{ TC}$
- **Bảng điểm hiện tại:**

| STT | Mã HP | Tên học phần | Số TC ($TC_i$) | Điểm chữ | Điểm số ($g_i$) | Điểm HP ($g_i \times TC_i$) | Độ khó ($d_i$) | Nhóm rủi ro ($K_1$) |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | `MATH101` | Giải tích 1 | 3 | **F** | 0.0 | 0.0 | 8 | **Nhóm 1** |
| 2 | `COMP102` | Lập trình C/C++ | 4 | **D** | 1.0 | 4.0 | 4 | **Nhóm 2** |
| 3 | `COMP211` | Cấu trúc dữ liệu | 4 | **C** | 2.0 | 8.0 | 5 | **Nhóm 2** |
| 4 | `COMP122` | Toán rời rạc | 3 | **C** | 2.0 | 6.0 | 4 | **Nhóm 2** |
| 5 | `POLI101` | Triết học Mác - Lênin | 3 | **C+** | 2.5 | 7.5 | 7 | **Nhóm 3** |
| 6 | `COMM101` | Kỹ năng giao tiếp | 2 | **C+** | 2.5 | 5.0 | 2 | **Nhóm 3** |
| 7 | `ENGL101` | Tiếng Anh 1 | 3 | **B** | 3.0 | 9.0 | 6 | **Nhóm 3** |
| 8 | `PHYE101` | Điền kinh | 1 | **B** | 3.0 | 3.0 | 1 | **Nhóm 3** |
| 9 | `COMP101` | Tin học đại cương | 3 | **B+** | 3.5 | 10.5 | 3 | **Nhóm 3** |
| 10 | `COMP293` | Cơ sở dữ liệu | 4 | **A** | 4.0 | 16.0 | 6 | *Đã đạt A* |
| 11 | `MATH159` | Đại số tuyến tính | 3 | **A** | 4.0 | 12.0 | 7 | *Đã đạt A* |
| 12 | `PSYC101` | Tâm lý học đại cương | 3 | **A** | 4.0 | 12.0 | 4 | *Đã đạt A* |
| 13 | `COMP301` | Mạng máy tính | 3 | **A** | 4.0 | 12.0 | 5 | *Đã đạt A* |
| 14 | `DEFE101` | Giáo dục quốc phòng 1 | 3 | **A** | 4.0 | 12.0 | 3 | *Đã đạt A* |
| 15 | `DEFE102` | Giáo dục quốc phòng 2 | 3 | **A** | 4.0 | 12.0 | 3 | *Đã đạt A* |

- **Tính toán hiện tại:**
  $$\text{Points}_{\text{current}} = 0 + 4 + 8 + 6 + 7.5 + 5 + 9 + 3 + 10.5 + 16 + 12 + 12 + 12 + 12 + 12 = 129.0$$
  $$\text{CPA}_{\text{current}} = \frac{129.0}{45} = \mathbf{2.867} \quad (\text{Xếp loại Khá})$$

- **Mục tiêu đặt ra:** Đạt loại **Giỏi** ($\text{CPA}_{\text{target}} = \mathbf{3.20}$).

---

### 4.2. Quá trình tính toán chi tiết của thuật toán

#### Bước 1: Tính lượng điểm cần bù đắp
$$\text{Points}_{\text{target}} = 3.20 \times 45 = 144.0$$
$$\Delta_{\text{Total}} = 144.0 - 129.0 = \mathbf{15.0\text{ điểm chất lượng}}$$

#### Bước 2: Lập bảng phân tích tiềm năng và sắp xếp ứng viên

Loại các môn đã đạt A (`COMP293`, `MATH159`, `PSYC101`, `COMP301`, `DEFE101`, `DEFE102`), còn lại 9 môn ứng viên:

| Thứ tự | Mã HP | Tên môn học | $TC_i$ | Điểm | $g_i$ | $\Delta_{i,A} = (4.0-g_i) \times TC_i$ | $\Delta_{i,B+} = (3.5-g_i) \times TC_i$ | Độ khó ($d_i$) | Nhóm ($K_1$) | Tiêu chí quyết định thứ hạng |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **1** | `MATH101` | Giải tích 1 | 3 | F | 0.0 | **12.0** | 10.5 | 8 | **1** | Nhóm 1 (Điểm F bắt buộc) |
| **2** | `COMP102` | Lập trình C/C++ | 4 | D | 1.0 | **12.0** | 10.0 | 4 | **2** | Nhóm 2, $\Delta_{i,A}=12.0$ |
| **3** | `COMP211` | Cấu trúc dữ liệu | 4 | C | 2.0 | **8.0** | 6.0 | 5 | **2** | Nhóm 2, $\Delta_{i,A}=8.0$ (dễ=5) |
| **4** | `COMP122` | Toán rời rạc | 3 | C | 2.0 | **6.0** | 4.5 | 4 | **2** | Nhóm 2, $\Delta_{i,A}=6.0$ (dễ=4) |
| **5** | `COMM101` | Kỹ năng giao tiếp | 2 | C+ | 2.5 | **3.0** | 2.0 | 2 | **3** | Nhóm 3, $\Delta_{i,A}=3.0, d=2$ (dễ hơn) |
| **6** | `ENGL101` | Tiếng Anh 1 | 3 | B | 3.0 | **3.0** | 1.5 | 6 | **3** | Nhóm 3, $\Delta_{i,A}=3.0, d=6, TC=3$ |
| **7** | `POLI101` | Triết học Mác | 3 | C+ | 2.5 | **4.5** | 3.0 | 7 | **3** | Nhóm 3, $\Delta_{i,A}=4.5, d=7$ |
| **8** | `PHYE101` | Điền kinh | 1 | B | 3.0 | **1.0** | 0.5 | 1 | **3** | Nhóm 3, $\Delta_{i,A}=1.0, d=1$ |
| **9** | `COMP101` | Tin học ĐC | 3 | B+ | 3.5 | **1.5** | 0.0 | 3 | **3** | Nhóm 3, $\Delta_{i,A}=1.5, d=3$ |

#### Bước 3: Thực hiện lựa chọn tham lam (Greedy Selection)

- **Cần bù đắp ban đầu:** $R = 15.0$

- **Lựa chọn 1:** Xét môn thứ 1: **`MATH101` (Giải tích 1, 3 TC, F $\rightarrow$ 0.0)**
  - Đòn bẩy tối đa khi lên A: $\Delta_{1,A} = 12.0$.
  - Vì $12.0 < 15.0$ (chưa đủ bù hết $R$), môn này bắt buộc phải nỗ lực đạt **A**.
  - Điểm bù được: $+12.0$.
  - Điểm còn thiếu: $R' = 15.0 - 12.0 = \mathbf{3.0}$.
  - 👉 **Gợi ý môn 1:** `MATH101 - Giải tích 1` $\rightarrow$ **[🎯 Cải thiện ➔ A]**

- **Lựa chọn 2:** Xét môn thứ 2: **`COMP102` (Lập trình C/C++, 4 TC, D $\rightarrow$ 1.0)**
  - Lượng điểm còn thiếu chỉ là $R' = 3.0$.
  - Kiểm tra nếu chỉ cải thiện lên **B+ (3.5)**:
    $$\Delta_{2,B+} = (3.5 - 1.0) \times 4 = 10.0 \ge 3.0 \quad (\text{ĐÃ THỪA THỎA MÃN!})$$
  - Do đó, sinh viên **không nhất thiết phải đạt A**, chỉ cần đạt điểm **B+** là đã vượt mục tiêu CPA!
  - Điểm bù được khi lên B+: $+10.0$.
  - Điểm còn thiếu: $R'' = 3.0 - 10.0 = -7.0 \le 0$ (**HOÀN THÀNH MỤC TIÊU**).
  - 👉 **Gợi ý môn 2:** `COMP102 - Lập trình C/C++` $\rightarrow$ **[🎯 Cải thiện ➔ B+]**

- **Dừng thuật toán:** Tổng số môn cần học lại là **đúng 2 môn** (tổng 7 tín chỉ) thay vì phải học lại tràn lan 5-6 môn.

---

### 4.3. Kiểm chứng kết quả CPA sau cải thiện

| Môn học cải thiện | Tín chỉ | Điểm cũ | Điểm mới sau cải | Điểm HP cũ | Điểm HP mới | Độ lệch tăng ($\Delta$) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `MATH101` (Giải tích 1) | 3 | F (0.0) | **A (4.0)** | 0.0 | 12.0 | +12.0 |
| `COMP102` (Lập trình C/C++) | 4 | D (1.0) | **B+ (3.5)** | 4.0 | 14.0 | +10.0 |
| **Tổng cộng** | **7 TC** | | | **4.0** | **26.0** | **+22.0** |

- **Tổng điểm tích lũy mới:**
  $$\text{Points}_{\text{new}} = \text{Points}_{\text{current}} + \Delta = 129.0 + 22.0 = \mathbf{151.0}$$
- **CPA mới sau khi cải thiện 2 môn:**
  $$\text{CPA}_{\text{new}} = \frac{151.0}{45} = \mathbf{3.355} \ge 3.20 \quad (\mathbf{ĐẠT\ XẾP\ LOẠI\ GIỎI\ VƯỢT\ CHỈ\ TIÊU!})$$

---

## 5. ĐÁNH GIÁ ĐỘ PHỨC TẠP VÀ HIỆU NĂNG HỆ THỐNG

1. **Độ phức tạp thời gian (Time Complexity):**
   - Lọc ứng viên: $O(m)$ với $m \le 92$ môn trong CTĐT.
   - Sắp xếp với 5 tiêu chí: $O(m \log m)$.
   - Chọn tham lam và gán nhãn: $O(m)$.
   - $\rightarrow$ Tổng thời gian tính toán: $O(m \log m) \approx 0.15\text{ ms}$, thực thi tức thời (0ms) trên cả Browser (Client-side JavaScript) và Django Server (Python backend).

2. **Tính tất định (Determinism):**
   - Nhờ tiêu chí $K_5$ (thứ tự từ điển tiếng Việt `localeCompare`), thuật toán đảm bảo trả về duy nhất 1 kết quả nhất quán trên mọi nền tảng, không bị nhảy kết quả ngẫu nhiên giữa các lần tải trang.

3. **Tính ứng dụng thực tiễn:**
   - Thuật toán giúp sinh viên tiết kiệm tối đa học phí và thời gian học lại, giảm tải cho phòng đào tạo trong khâu xếp lớp và hạn chế tối đa rủi ro bị hủy học phần do bộ lọc ảo đăng ký tín chỉ.

---
*Tài liệu được biên soạn và chuẩn hóa phục vụ công tác đào tạo và nghiên cứu kỹ thuật hệ thống HNUE OJ.*
