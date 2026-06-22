"""Phần thực hành chuyên sâu — bổ sung cho 7 bước chatbox PTT."""

ADS_PRACTICE = """
---

### H. ÁP DỤNG THỰC TẾ — Lộ trình 14 ngày (Bước 1)

| Ngày | Việc | Output cụ thể | Ai làm |
|---|---|---|---|
| D1 | Brief 1 trang + ICP | Google Doc brief signed | MKT Lead |
| D2 | Viết 3 variant Meta + 3 RSA set | Sheet copy_draft | Copy/Ads |
| D3 | Brief visual designer | Figma brief 1:1 + 9:16 | Creative |
| D4 | Setup campaign shell | Campaign/ad set structure | Ads Ops |
| D5 | QA tracking | Pixel + CAPI + 1 test lead | Ads + Dev |
| D6–D13 | Chạy A/B, pacing daily | Daily log spend/CPL | Ads |
| D14 | Review + quyết định | Scale 1 variant / iterate | MKT Lead |

### I. Brief 1 trang (copy template)

```
DỰ ÁN: [Tên chiến dịch] | MỤC TIÊU: Lead gen
ICP: [Ngành], [Quy mô NV], [Địa lý], [Job title]
PAIN: [1 câu pain chính]
OFFER: [Audit miễn phí / Pilot 4 tuần / Tải case]
LANDING: [URL] — CTA: [Form / Zalo / Gọi]
NGÂN SÁCH TEST: [VNĐ/kênh/14 ngày]
KPI: CPL ≤ [X]k | CVR landing ≥ [Y]%
COMPETITOR MESSAGE: [2–3 góc đối thủ]
RÀNG BUỘC: [Không claim X / ngành hạn chế]
```

### J. Cấu trúc campaign Meta (thực tế)

| Cấp | Quy tắc đặt tên | Ví dụ |
|---|---|---|
| Campaign | `[Mục tiêu]_[Quý]_[Sản phẩm]` | `LEAD_Q2_MARTECH` |
| Ad set | `[Audience]_[Placement]` | `ICP_B2B_Feed` |
| Ad | `[Variant]_[Format]` | `A_PAIN_Carousel` |

**CBO vs ABO:** Test tuần 1 dùng **ABO** (budget ad set) — kiểm soát variant. Scale tuần 3+ cân nhắc CBO.

### K. Checklist QA trước khi bật ads

- [ ] Landing mobile ≥90 PageSpeed (form above fold)
- [ ] Form ≤4 field (Tên, SĐT, Email, Công ty)
- [ ] Thank-you page fire conversion event
- [ ] UTM preview: mọi link ads có đủ 4 param
- [ ] Exclusion: customer list / employee upload
- [ ] Policy: không claim tuyệt đối ("#1", "100%") nếu chưa duyệt legal

### L. Công thức theo dõi hàng ngày

- **CPL** = Spend ÷ Leads
- **CVR** = Leads ÷ Clicks × 100%
- **Chi phí/MQL** = Spend ÷ MQL (sau scoring Bước 4)

**Quy tắc pause:** Variant CPL > target × 1.3 trong 5 ngày liên tiếp → pause, không tắt campaign.

### M. Lỗi thường gặp & cách fix

| Lỗi | Dấu hiệu | Fix thực tế |
|---|---|---|
| Creative fatigue | Frequency >3, CTR giảm | Refresh 2 creative/tuần |
| Landing mismatch | CTR cao, CVR <1% | Đổi headline landing khớp ad |
| Tracking lỗi | Ads báo lead, CRM = 0 | QA CAPI + form webhook |
| Broad quá rộng | CPL thấp, SQL rate <10% | Thu audience + scoring |

**Tuần 2:** Sang **Bước 7** đăng ký test headline · **Bước 4** gắn MQL scoring.
"""

TVC_PRACTICE = """
---

### H. Lộ trình sản xuất thực tế (21 ngày)

| Tuần | Công việc | Deliverable |
|---|---|---|
| W1 D1–2 | Brief + script v1 | Brief 1 trang + beat sheet |
| W1 D3–4 | Duyệt nội bộ + legal | Script v2 signed |
| W1 D5 | Pre-prod: casting, location | Shot list + schedule |
| W2 | Quay TVC + KOL | Raw footage |
| W3 D1–3 | Edit + color + supers | Master 16:9 + 9:16 |
| W3 D4 | QA legal + brand | Final export |
| W3 D5 | Upload + UTM + schedule | Live + tracking |

### I. Brief creative 1 trang (template)

```
BIG IDEA: [1 câu]
KEY MESSAGE: [3 bullet proof points]
TARGET: [Persona — pain, kênh xem video]
KPI: VTR ≥25% | Brand search +X% | CPL ref ≤250k
TONE: [Chuyên nghiệp / Năng động / Tin cậy]
MANDATORY: Logo 3s cuối | Hotline | Disclaimer [nếu có]
DELIVERABLE: TVC 30s | KOL 75s | 9:16 cut | Phụ đề VI
DEADLINE AIR: [DD/MM]
```

### J. Shot list thực địa (rút gọn TVC)

| # | Shot | Type | Thiết bị | Ghi chú |
|---|---|---|---|---|
| 1 | Marketer nhìn dashboard | CU | Gimbal | Hook 0–3s |
| 2 | Team họp chiến lược | Wide | Tripod | B-roll |
| 3 | Screen landing scroll | Screen rec | 4K | Che data |
| 4 | Handshake / CTA | MS | Gimbal | Proof |
| 5 | Logo end card | Graphic | AE | 3s hold |

### K. KPI đo sau launch

| Kênh | Metric | Công cụ | Review |
|---|---|---|---|
| YouTube pre-roll | VTR 30s | Ads Manager | D+7 |
| KOL post | Reach, CTR link | Insight + UTM | D+3, D+7 |
| Landing ref | CPL, CVR | GA4 + CRM | Weekly |

### L. Hợp đồng KOL — checklist pháp lý

- [ ] Quyền sử dụng video 12 tháng (paid boost)
- [ ] Duyệt script trước quay — 1 vòng revision
- [ ] Không claim số liệu chưa có proof
- [ ] #ad / sponsored tag theo quy định platform
- [ ] UTM riêng: `utm_source=kol&utm_medium=[ten_kol]`

**Handoff:** Asset final → **Bước 6** lịch phát sinh · **Bước 3** Excel tuần launch.
"""

EXCEL_PRACTICE = """
---

### H. Cách vận hành file Excel hàng ngày

**Sáng (10 phút):** Mở sheet `Ke_hoach_tuan` — lọc tuần hiện tại + owner = bạn → cập nhật Trạng thái.

**Chiều T4 (20 phút):** Ads lead điền KPI thực tế spend/CPL · so sánh pacing:
- Pacing % = Đã chi tuần ÷ Ngân sách tuần × 100%
- Nếu >110% giữa tuần → giảm daily cap 15%

**T6 họp 30' (agenda cố định):**
1. KPI tuần vs mục tiêu (5')
2. Top 3 learnings (5')
3. Quyết định scale/pause/kill (10')
4. Chốt W+1 priority (10')

### I. Sheet Rui_ro_tuan (thêm vào file)

| Rủi ro | P | I | P×I | Mitigation | Owner | Deadline |
|---|---|---|---|---|---|---|
| Pixel lỗi | 2 | 5 | 10 | QA checklist D1 | Dev | [date] |
| Creative fatigue | 4 | 3 | 12 | Refresh T2 hàng tuần | Social | Recurring |
| Sales SLA miss | 3 | 4 | 12 | Alert CRM >4h | Sales lead | [date] |

### J. Công thức Excel gợi ý

```
KPI thực tế CPL: =Tổng_chi_tuần/Tổng_lead
% hoàn thành KPI: =IF(KPI_mục_tiêu>0, KPI_thực_tế/KPI_mục_tiêu, "")
Burn rate tháng: =SUM(Đã_chi)/SUM(Ngân_sách_kế_hoạch)
```

### K. Mẫu báo cáo tuần (copy vào email T6)

```
BÁO CÁO MARKETING TUẦN [Wx] — [Brand]
1. Spend: [X]M / Kế hoạch [Y]M ([Z]%)
2. Lead/MQL/SQL: [a]/[b]/[c]
3. CPL trung bình: [k] (target [t]k)
4. Kênh tốt nhất: [kênh] — CPL [x]k
5. Kênh cần fix: [kênh] — lý do
6. Quyết định W+1: [scale/pause/test]
7. Blocker cần hỗ trợ: [nếu có]
```

### L. RACI tuần

| Hạng mục | MKT Lead | Ads | Content | Sales | Finance |
|---|---|---|---|---|---|
| Kế hoạch tuần | A | R | R | C | I |
| Pacing budget | A | R | C | I | C |
| KPI review T6 | A | R | R | R | I |
| Reforecast tháng | A | C | C | C | R |

**A**=Accountable · **R**=Responsible · **C**=Consulted · **I**=Informed

Tải mẫu: nút **XLS** → điền W1 trong ngày · gắn KPI **Bước 4**.
"""

FUNNEL_PRACTICE = """
---

### H. Triển khai CRM thực tế (tuần 1–2)

| Ngày | Task CRM | Chi tiết |
|---|---|---|
| D1 | Tạo pipeline stage | KHTN → MQL → SQL → Opp → Win → CSKH |
| D2 | Form fields + hidden UTM | 5 field + utm_source/medium/campaign |
| D3 | Scoring rules | Bảng điểm Bước 4 — automation |
| D4 | Email D0 template | Subject + body case ngành |
| D5 | SLA task telesales | Task auto assign SDR, due 4h |
| D6 | Test end-to-end | 1 lead giả → verify full flow |

### I. Email nurture D0–D14 (mẫu thực tế)

**D0 (≤1h sau form):** Subject: `[Tên], tài liệu [ngành] anh/chị quan tâm`
- Body: cảm ơn + 1 case PDF + CTA book 15' call

**D2:** Subject: `3 lỗi thường gặp khiến CPL cao (và cách fix)`
- Body: checklist + link blog

**D7:** Subject: `Lịch demo 30 phút — tuần này còn 2 slot`
- Body: social proof + calendar link

**D14:** Subject: `Tóm tắt giá trị pilot 4 tuần PTT`
- Body: offer cụ thể + last CTA

### J. SLA sales — vận hành hàng ngày

| Khung giờ | Việc SDR |
|---|---|
| 8h30 | Xem queue MQL mới + MQL quá hạn SLA |
| 9h–11h | Block gọi outbound (batch 1) |
| 14h–16h | Block gọi (batch 2) + log CRM |
| 17h | Zero inbox — 100% lead có next step |

**Escalation:** MQL >4h chưa contact → notify Sales Lead trên Slack/Zalo.

### K. Dashboard funnel (tính hàng tuần)

| Metric | Công thức | Mục tiêu B2B |
|---|---|---|
| MQL rate | MQL ÷ Leads | ≥50% |
| MQL→SQL | SQL ÷ MQL | ≥25% |
| SQL→Win | Win ÷ SQL | ≥20% |
| Velocity | AVG(win_date - lead_date) | ≤45 ngày |
| CAC | Total MKT spend ÷ Wins | ≤ LTV/3 |

```chart-json
{"type":"bar","title":"Funnel conversion (minh họa)","labels":["Lead→MQL","MQL→SQL","SQL→Win"],"values":[52,28,22]}
```

### L. Lỗi funnel thường gặp

| Triệu chứng | Nguyên nhân | Fix |
|---|---|---|
| Nhiều lead, ít SQL | Scoring quá lỏng / sales reject | Thu scoring + đồng bộ tiêu chí SQL |
| SQL không win | Demo yếu / proposal chậm | Template demo + SLA proposal 48h |
| MQL nurture không mở | Subject chung chung | A/B subject Bước 7 |

**Handoff Bước 5:** Script telesales cho SLA ≤4h · **Bước 3:** log KPI funnel mỗi T6.
"""

TELESALES_PRACTICE = """
---

### H. Vận hành đội telesales (SOP hàng ngày)

**Trước 9h:** SDR mở CRM → tab "MQL cần gọi hôm nay" (sort: SLA gần hết).

**Mỗi cuộc gọi:** Mở script Bước 5 + form CRM bên cạnh → log ngay khi cúp máy.

**Cuối ngày:** 100% cuộc gọi có outcome · 0 lead MQL quá 4h không touch.

### I. Script xử lý phản đối — thoại đầy đủ

**"Gửi báo giá email đi":**
> "Dạ em gửi được ạ. Để báo giá sát ngành và quy mô team mình, em xin 20 phút demo — em chuẩn bị 1 trang scope riêng, không phải bảng giá chung chung. Thứ [X] [giờ] hoặc [Y] [giờ] anh/chị tiện hơn ạ?"

**"Đang dùng agency khác":**
> "Dạ em hiểu. Nhiều anh/chị giữ agency hiện tại và nhờ PTT audit một mảng — tracking hoặc creative — 4 tuần, không ảnh hưởng hợp đồng cũ. Anh/chị muốn em gửi checklist audit miễn phí trước không ạ?"

### J. CRM log template (copy sau mỗi cuộc gọi)

```
Lead: [ID] [Tên] | Nguồn: [utm]
Outcome: [Connected/No answer/Wrong/Busy/Not interested]
Pain chính: [1 dòng]
Objection: [giá/timing/đối thủ/budget/không cần]
SPIN note: [Situation/Problem ghi rút gọn]
Next step: [Demo T3 10h / Gửi case / Gọi lại T5]
Deadline next: [DD/MM HH:mm]
```

### K. KPI SDR (review tuần)

| KPI | Mục tiêu | Cách đo |
|---|---|---|
| Contact rate | ≥60% MQL | Connected ÷ MQL assigned |
| Demo book rate | ≥30% connected | Demo booked ÷ Connected |
| Show rate | ≥70% | Demo attended ÷ Booked |
| SLA compliance | ≥95% | Gọi ≤4h ÷ Total MQL |

### L. Cadence follow-up (không bắt máy)

| Lần | Thời điểm | Kênh | Nội dung |
|---|---|---|---|
| 1 | D0 +2h | Gọi lại | — |
| 2 | D+1 sáng | Gọi + Zalo | "Em gửi case [ngành]" |
| 3 | D+2 | Email | Case study + calendar |
| 4 | D+5 | Gọi cuối | Chuyển nurture dài hạn |

Sau 3 lần không liên hệ được → tag `nurture_long` · automation email Bước 4.

**Kết nối:** KPI log vào **Bước 3** Excel · SQL rate feed **Bước 7** test chất lượng lead.
"""

MULTICHANNEL_PRACTICE = """
---

### H. Workshop lập KH 3 tháng (1 buổi — agenda 3h)

| Block | Thời lượng | Output |
|---|---|---|
| 1. SMART + ICP | 30' | 1 trang mục tiêu số |
| 2. Insight + Big Idea | 30' | Key message 3 funnel |
| 3. Channel mix | 45' | Ma trận P/O/E filled |
| 4. Budget phân bổ | 30' | Pie chart + cap/kênh |
| 5. Lịch phát sinh T1 | 30' | Calendar W1–W4 |
| 6. Measurement plan | 15' | UTM doc + dashboard |

### I. Key message theo funnel (mẫu điền)

| Funnel | Insight KH | Message | Proof | CTA |
|---|---|---|---|---|
| Awareness | "Ads tốn mà không đo được" | Creative Martech — đo được từng kênh | 200+ dự án | Xem video |
| Consideration | "Agency báo cáo chậm" | Báo cáo KPI hàng tuần minh bạch | Case CPL ↓35% | Tải case |
| Conversion | "Cần lead chất lượng" | Audit funnel miễn phí 30 phút | Testimonial | Đặt lịch |
| Retention | "Scale không kiểm soát" | Pilot 4 tuần trước scale | Process doc | Họp QBR |

### J. Quy tắc phân bổ ngân sách thực tế

| Bucket | % | Khi nào dùng |
|---|---|---|
| Base (validate) | 60–70% | Kênh đạt CPL target ≥14 ngày |
| Test | 20–25% | Variant mới, kênh mới |
| Reserve | 10–15% | Seasonality, bid war, opportunity |
| Brand (optional) | 5–10% | TVC/KOL/PR |

**Reallocate T6:** Chuyển max 20% budget từ kênh CPL >target 20% sang kênh thắng.

### K. Báo cáo cross-channel T6 (template)

| Kênh | Spend | Leads | MQL | SQL | CPL | ROMI note |
|---|---|---|---|---|---|---|
| Google | | | | | | |
| Meta | | | | | | |
| ... | | | | | | |

**3 insight tuần:** 1) … 2) … 3) …
**Quyết định tuần sau:** Scale [X] · Pause [Y] · Test [Z]

### L. Đồng bộ UTM — doc team (copy)

```
Quy ước: utm_source / utm_medium / utm_campaign / utm_content
Ví dụ Google: google / cpc / leadgen_q2 / rsa_variant_a
Ví dụ Meta: facebook / paid / leadgen_q2 / carousel_case
Ví dụ Email: crm / email / nurture_d2 / subject_b
CRM map: custom field Source = utm_source + campaign
```

Tải Excel: nút **ĐK** · Chạy test: **Bước 7** trước khi scale T2 tháng 2.
"""

CHANNEL_TEST_PRACTICE = """
---

### H. Quy trình test trong team (weekly test review)

**Thứ 3 hàng tuần — 20 phút Test Standup:**
1. Test đang chạy — đủ mẫu chưa?
2. Test tuần trước — Scale / Iterate / Kill?
3. Đăng ký test mới tuần này (1 biến số/test)

### I. Mẫu đăng ký test (copy vào Test_matrix)

```
ID: TEST-[YYYY]-[NN]
Owner: [Tên]
Kênh: [Google/Meta/...]
Giả thuyết: Nếu [thay đổi X] thì [metric Y] cải thiện ≥[Z]%
Biến số duy nhất: [creative / headline / audience / landing / subject]
Control: [Mô tả A]
Variant: [Mô tả B] (Variant C nếu có)
Ngày bắt đầu: [DD/MM] | Kết thúc dự kiến: [DD/MM]
Min sample: [N] [click/conversion/view]
Primary metric: [CPL/CVR/Open/...]
Ngưỡng thắng: [Cụ thể — vd CPL ≤ control × 0.85]
Secondary: [SQL rate không giảm >5%]
Trạng thái: [Planned/Running/Analyzing/Done]
Kết quả: [Số liệu control vs variant]
Quyết định: [Scale 25% / Iterate / Kill]
Bài học: [1–2 câu]
```

### J. Cách tính mẫu tối thiểu (thực tế)

| Loại test | Rule of thumb |
|---|---|
| CPL comparison | ≥30 conversion/variant (tối thiểu) · lý tưởng ≥50 |
| CTR A/B landing | ≥200 click/variant |
| Email open rate | ≥1.000 recipient/branch · 95% confidence ~10% lift |
| TikTok hook | ≥50.000 view/variant trước kết luận |

**Không dừng sớm** vì "thấy variant tốt hơn ngày 3" — trừ khi spend vượt cap an toàn.

### K. Scale protocol (khi thắng)

1. Tuần 1 thắng: +20% budget variant thắng
2. Tuần 2 vẫn đạt ngưỡng: +20% nữa (tổng ~44%)
3. Monitor SQL rate — nếu giảm >5% → dừng scale, iterate landing
4. Ghi log vào Excel **Bước 3** + **Test_matrix**

### L. Post-mortem test FAIL (template)

```
Test ID: [ ]
Giả thuyết ban đầu: [ ]
Kết quả thực tế: Control [x] vs Variant [y]
Lý do fail (root cause): [creative/message/audience/tracking/sample nhỏ]
Hành động tiếp: [Iterate biến số mới / Chuyển sang kênh khác / Kill]
Owner iteration: [ ] Deadline: [ ]
```

```chart-json
{"type":"line","title":"CPL theo ngày — test headline (minh họa)","labels":["D1","D3","D5","D7","D10","D14"],"values":[320,290,265,250,242,235]}
```

**Chu trình:** Test (B7) → Scale winner → Cập nhật Excel (B3) → Điều chỉnh mix (B6).
"""

PRACTICE_BY_STEP: dict[str, str] = {
    "ads_copy": ADS_PRACTICE,
    "tvc_kol": TVC_PRACTICE,
    "excel_weekly": EXCEL_PRACTICE,
    "funnel": FUNNEL_PRACTICE,
    "telesales": TELESALES_PRACTICE,
    "multichannel_plan": MULTICHANNEL_PRACTICE,
    "channel_test": CHANNEL_TEST_PRACTICE,
}


def append_practice(base_template: str, step_id: str) -> str:
    extra = PRACTICE_BY_STEP.get(step_id, "").strip()
    if not extra:
        return base_template
    return base_template.rstrip() + "\n" + extra
