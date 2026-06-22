"""Template chi tiết cho 7 bước thực thi marketing — chatbox CMS PTT."""
from __future__ import annotations

import re

from marketing_step_practice import PRACTICE_BY_STEP, append_practice

STEP_TAG_RE = re.compile(r"\[BUOC:([\w_]+)\]", re.IGNORECASE)


def extract_step_id(question: str) -> str | None:
    m = STEP_TAG_RE.search(str(question or ""))
    return m.group(1).lower() if m else None


def step_trigger(module_id: str, prompt: str = "") -> str:
    return f"[BUOC:{module_id}] {prompt}".strip()


# ---------------------------------------------------------------------------
# Bước 1 — Mẫu FB / Google Ads
# ---------------------------------------------------------------------------
ADS_TEMPLATE = """**BƯỚC 1 — Mẫu Facebook Ads & Google Ads (triển khai chi tiết)**

### A. Mục tiêu bước này
- Soạn **≥3 biến thể copy** mỗi kênh, sẵn sàng upload lên Ads Manager / Google Ads.
- Gắn **UTM + pixel/CAPI** để đo CPL theo variant ngay từ ngày 1.
- Chuẩn bị **brief creative** (tỷ lệ, hook, CTA) cho designer/video.

### B. Input cần chuẩn bị
| Hạng mục | Ví dụ / ghi chú |
|---|---|
| Mục tiêu chiến dịch | Lead gen / Brand / Traffic |
| ICP / ngành | B2B dịch vụ, 20–200 NV, HCM/HN |
| Pain chính | CPL cao, lead kém chất lượng, thiếu tracking |
| Offer | Audit funnel miễn phí 30 phút / Pilot 4 tuần |
| Landing URL | Trang có form + thank-you page |
| Ngân sách test | 10–15M/kênh / 14 ngày |

### C. Quy trình 7 bước con
1. **Chốt 1 pain + 1 offer** — không quá 2 offer trong 1 campaign.
2. **Viết 3 góc tiếp cận:** Pain hook · Social proof · Offer cụ thể.
3. **Meta:** primary (≤125 ký tự hook) + 3 headline (≤40) + mô tả link + CTA Lead.
4. **Google RSA:** 3 headline (≤30) + 2 description (≤90) + extensions (sitelink, callout, snippet).
5. **Brief visual:** 1:1 feed, 9:16 story/reels; ghi chú text overlay tối đa 20% (Meta).
6. **Gắn UTM** theo chuẩn PTT (bảng dưới) + kiểm tra pixel Lead event.
7. **A/B tuần 1:** chạy 3 variant song song, ngân sách chia đều, review sau 7 ngày.

### D. Copy mẫu — Facebook Ads (3 biến thể)

**Variant A — Pain hook**
- Primary: CPL vẫn cao dù đã tăng budget? PTT audit funnel + creative theo data — đặt lịch 30 phút miễn phí.
- Headline 1: Giảm CPL — Audit miễn phí | H2: Creative Martech B2B | H3: Tư vấn ads đa kênh
- CTA: Đăng ký · Visual: Dashboard before/after CPL

**Variant B — Social proof**
- Primary: 200+ dự án đa kênh — SEO/AEO đến performance ads. Nhận lộ trình 1 trang theo ngành.
- Headline: Case thực tế — CPL ↓ 35%

**Variant C — Offer pilot**
- Primary: Pilot 4 tuần: 2 creative + 1 landing + QA tracking. Báo cáo CPL/ROAS hàng tuần.
- Headline: Pilot ads 4 tuần — KPI minh bạch

### E. Copy mẫu — Google Search RSA

| Thành phần | Nội dung |
|---|---|
| Headline 1–3 | Dịch vụ quảng cáo Google · Tối ưu CPL PTT · Audit ads miễn phí |
| Description 1–2 | Creative Martech — chiến lược, creative & đo lường. Performance ads + landing chuẩn CVR. |
| Extensions | Sitelink: SEO/AEO/Case · Callout: Báo cáo tuần, Tracking chuẩn · Snippet: Dịch vụ |

**UTM chuẩn:** `utm_source=facebook|google&utm_medium=paid&utm_campaign=leadgen_q2&utm_content=variant_a`

### F. KPI & ngưỡng (tuần 1–2)

| Metric | Mục tiêu | Hành động nếu lệch |
|---|---|---|
| CTR (Search) | ≥3% | Đổi headline RSA |
| CTR (Meta) | ≥1% | Đổi hook visual 3s đầu |
| CPL | ≤ ngưỡng brief | Pause variant >+30% CPL |
| Landing CVR | ≥3% | Chuyển sang bước 4 — test landing |

```chart-json
{"type":"bar","title":"CPL theo variant (minh họa tuần 1)","labels":["Variant A","Variant B","Variant C"],"values":[220,195,248]}
```

### G. Checklist hoàn thành → sang Bước 7 (test)
- [ ] 3 variant Meta + 3 RSA headline set đã duyệt
- [ ] UTM + pixel/CAPI test OK (1 lead giả lập)
- [ ] Brief visual gửi designer kèm deadline
- [ ] Sheet log test (variant / spend / CPL) — dùng Excel **ĐK** hoặc **Test_matrix**

**Bước tiếp theo:** Bấm **7. Phương pháp test kênh** để đăng ký giả thuyết & ngưỡng scale.
"""

# ---------------------------------------------------------------------------
# Bước 2 — TVC & KOL
# ---------------------------------------------------------------------------
TVC_KOL_TEMPLATE = """**BƯỚC 2 — Kịch bản TVC 30s & Video KOL (triển khai chi tiết)**

### A. Mục tiêu bước này
- Có **beat sheet duyệt được** trước khi quay (timecode | visual | audio | supers).
- TVC 30s + KOL 60–90s **cùng Big Idea**, khác format (mass reach vs trust).
- Deliverable: script, shot list, checklist post-production, CTA thống nhất landing.

### B. Input cần chuẩn bị
- Big Idea / key message (1 câu)
- Phân khúc & kênh phát (TV/YouTube/KOL platform)
- Tone: B2B chuyên nghiệp / FMCG năng động
- Ràng buộc: logo, disclaimer, ngành hạn chế quảng cáo
- Budget quay & deadline air date

### C. Quy trình 6 bước con
1. **Brief 1 trang:** mục tiêu (awareness/consideration), KPI (VTR, brand search, CPL ref).
2. **Viết TVC 30s** theo cấu trúc 0-3-20-27-30 giây.
3. **Viết KOL script** 60–90s: hook → context → demo → proof → soft CTA.
4. **Shot list & asset:** A-roll/B-roll ratio, phụ đề, format 16:9 + 9:16 cut-down.
5. **Pre-prod checklist:** duyệt script, location, talent, legal (claim/số liệu).
6. **Post-prod & launch:** supers, logo end-card, UTM link bio/landing, pixel view/lead.

### D. TVC 30s — Beat sheet chi tiết

| Time | Visual | Audio / VO | Supers | Note |
|---|---|---|---|---|
| 0–3s | CPL chart tăng, marketer lo | "Ngân sách ads tăng — lead chất lượng?" | CPL cao? | Hook visual mạnh |
| 3–12s | Team PTT + dashboard | "PTT — Creative Martech" | Data + Creative | USP |
| 12–22s | Landing, ads, báo cáo | "Audit → pilot → scale" | CPL↓ ROAS↑ | Proof montage |
| 22–27s | Khách hàng / handshake | "Đồng hành tăng trưởng" | 200+ dự án | Social proof |
| 27–30s | Logo + CTA | "Đặt lịch hôm nay" | URL + hotline | End card 3s |

### E. Video KOL 60–90s — Script chi tiết

| Phân đoạn | Thời lượng | Nội dung | Ghi chú sản xuất |
|---|---|---|---|
| Hook | 0–8s | "Mình từng đốt budget Meta mà lead toàn hỏi giá…" | Nhìn camera, caption hook |
| Context | 8–25s | Giới thiệu PTT — funnel + creative + tracking | B-roll văn phòng |
| Demo | 25–50s | Screen báo cáo tuần / landing before-after | Che data nhạy cảm |
| Proof | 50–65s | Quote khách / số liệu đã duyệt PR | Text overlay |
| CTA | 65–75s | "Link audit miễn phí ở bio" | UTM riêng KOL |

**Shot list:** A-roll 70% · B-roll 30% · Phụ đề VI bắt buộc · 9:16 cut từ master 16:9

### F. KPI & rủi ro

| KPI | Mục tiêu | Rủi ro | Giảm thiểu |
|---|---|---|---|
| VTR 30s (TVC) | ≥25% | Message không rõ 3s đầu | Test 2 hook pre-launch |
| View-through KOL | ≥50k | KOL không đúng ICP | Brief + duyệt script trước |
| CPL ref traffic | ≤250k | CTA yếu | A/B end-card + link tracked |

```mermaid
flowchart LR
  B[Brief] --> S[Script duyệt]
  S --> P[Pre-prod]
  P --> Q[Quay]
  Q --> PP[Post + QA legal]
  PP --> L[Launch + UTM]
```

### G. Checklist hoàn thành
- [ ] Beat sheet TVC + script KOL đã sign-off
- [ ] Shot list & timeline quay
- [ ] Legal duyệt claim/số liệu
- [ ] UTM + landing sẵn sàng trước ngày KOL đăng

**Bước tiếp theo:** Đưa asset vào **Bước 6** (lịch phát sinh đa kênh) và **Bước 3** (Excel tuần).
"""

# ---------------------------------------------------------------------------
# Bước 3 — Excel kế hoạch tuần
# ---------------------------------------------------------------------------
EXCEL_WEEKLY_TEMPLATE = """**BƯỚC 3 — Excel kế hoạch marketing theo tuần (triển khai chi tiết)**

### A. Mục tiêu bước này
- Vận hành **12 tuần** với 1 file duy nhất: kế hoạch · KPI · ngân sách · rủi ro.
- Mỗi tuần có **owner, deadline, KPI mục tiêu/thực tế, trạng thái** rõ ràng.
- Họp review **Thứ 6 hàng tuần** dựa trên sheet này.

### B. Cấu trúc file (4 sheet)
| Sheet | Mục đích | Ai cập nhật | Tần suất |
|---|---|---|---|
| `Ke_hoach_tuan` | Task theo tuần/kênh | Marketing lead | Daily/Weekly |
| `KPI_tong_hop` | Dashboard CPL/MQL/SQL/ROAS | Performance | Weekly |
| `Ngan_sach` | Plan vs actual spend | Finance/MKT | Weekly |
| `Rui_ro_tuan` | Rủi ro & hành động | MKT lead | Weekly |

### C. Cột sheet Ke_hoach_tuan (bắt buộc)

| Cột | Mô tả | Ví dụ |
|---|---|---|
| Tuần | W1–W12 | W1 |
| Kênh | Google/Meta/Email… | Google Search |
| Chiến dịch | Tên campaign | Lead gen Q2 |
| Hạng mục/Creative | Asset cụ thể | RSA 3 variant |
| Ngân sách (VNĐ) | Cap tuần | 15.000.000 |
| KPI mục tiêu | Định lượng | CPL ≤250k |
| KPI thực tế | Số liệu cuối tuần | 235k |
| Owner | 1 người chịu trách nhiệm | Ads Lead |
| Trạng thái | Planned/In progress/Done/Blocked | In progress |
| Ghi chú | Blocker, learnings | Đổi headline T4 |

### D. Mẫu điền W1–W4 (chi tiết)

| Tuần | Kênh | Chiến dịch | Hạng mục | NS (VNĐ) | KPI mục tiêu | Owner |
|---|---|---|---|---|---|---|
| W1 | Google Search | Lead Q2 | RSA + ext + QA tracking | 15M | CPL≤250k | Ads |
| W1 | Meta | Lead Q2 | 3 carousel case study | 12M | CPL≤180k | Social |
| W1 | Content | SEO pillar | 2 bài + internal link | 5M | 500 visit | Content |
| W1 | Email | Nurture | Sequence D0-D7 | 2M | Open≥25% | CRM |
| W2 | Google Display | Remarketing | 7-day audience | 8M | CPA≤300k | Ads |
| W2 | Meta | Retarget | Video 15s + lead form | 10M | CPL≤200k | Social |
| W2 | Telesales | SQL | Gọi MQL ≤4h SLA | 0 | Contact≥60% | Sales |
| W3 | Google | Scale | +20% ad set thắng | 18M | ROAS≥3 | Ads |
| W3 | Landing | CRO | A/B headline + form | 3M | CVR+15% | CRO |
| W4 | Review | Monthly | ROMI + reforecast Q | 0 | Báo cáo xong | MKT Lead |

### E. Ritual vận hành hàng tuần
| Ngày | Việc | Output |
|---|---|---|
| T2 | Kickoff tuần — chốt priority 3 task | Status Planned→In progress |
| T4 | Mid-week pacing — spend vs KPI | Điều chỉnh bid/budget |
| T6 | Weekly review — điền KPI thực tế | Quyết định scale/pause tuần sau |
| T6 | Cập nhật sheet Rui_ro_tuan | Owner + deadline fix |

```chart-json
{"type":"line","title":"Burn rate vs kế hoạch (minh họa)","labels":["W1","W2","W3","W4"],"values":[92,88,95,90]}
```

### F. Checklist hoàn thành
- [ ] Tải file mẫu — nút **XLS** trên toolbar chat
- [ ] Điền owner cho 100% dòng W1
- [ ] Link file trên drive nội bộ + quyền edit team
- [ ] Lịch họp T6 recurring 30 phút

**Bước tiếp theo:** **Bước 4** (funnel) để gắn KPI chuyển tiếp · **Bước 7** (test) cho tuần 2–3.
"""

# ---------------------------------------------------------------------------
# Bước 4 — Funnel
# ---------------------------------------------------------------------------
FUNNEL_TEMPLATE = """**BƯỚC 4 — Funnel Lead → Khách hàng (triển khai chi tiết)**

### A. Mục tiêu bước này
- Map **end-to-end** từ click ads → win → CSKH với SLA & automation.
- Định nghĩa **MQL scoring**, ngưỡng chuyển SQL, trigger nurture.
- KPI chuyển tiếp đo được trên CRM (PTT pipeline KHTN/KHQT/CSKH).

### B. Phân giai đoạn & định nghĩa

| Giai đoạn | Định nghĩa | Ngưỡng vào | Owner |
|---|---|---|---|
| **Visitor** | Click landing | — | Marketing |
| **Lead** | Submit form | — | Marketing |
| **MQL** | Lead đạt score | Score ≥60 | Marketing |
| **SQL** | Sales chấp nhận | SLA ≤4h contact | Sales |
| **Opportunity** | Demo xong + có budget | Proposal sent | Sales |
| **Win** | Ký HĐ | — | Sales |
| **CSKH** | Onboarding + NPS | Kickoff ≤7 ngày | CS |

### C. Touchpoint chi tiết

| Giai đoạn | Touchpoint | Hành động KH | Hành động team | KPI | SLA |
|---|---|---|---|---|---|
| KHTN | Ad → Landing | Click, đọc, form | A/B creative, UTM | CTR, CPL | — |
| KHTN | Form submit | Điền thông tin | Scoring, tag nguồn | MQL rate | Auto ≤5 phút |
| KHQT | Email D0/D2/D7 | Mở, click case | Nurture workflow | Open, click | D0 ≤1h |
| KHQT | Telesales | Nghe pitch | SPIN, book demo | Contact rate | **≤4h** |
| KHQT | Demo 30' | Tham dự | Custom deck | Show rate | Book ≤48h |
| KHQT | Proposal | Review BG | Follow D+2, D+5 | Win rate | — |
| CSKH | Onboarding | Kickoff | Handover kit | TTV ≤7 ngày | — |
| CSKH | QBR | Review KPI | Upsell Q+1 | NPS, retention | Quarterly |

### D. MQL scoring (mẫu)

| Tiêu chí | Điểm |
|---|---|
| Đúng ngành ICP | +20 |
| Quy mô 20–200 NV | +15 |
| Budget timeline ≤90 ngày | +25 |
| Job title decision-maker | +20 |
| Mở email D0 | +10 |
| **Ngưỡng MQL** | **≥60** |

### E. Automation & trigger

```mermaid
flowchart TD
  A[Form submit] --> B{Score ≥60?}
  B -->|Có| C[Assign SDR + task gọi 4h]
  B -->|Không| D[Nurture D0-D14]
  C --> E{Contact OK?}
  E -->|Có| F[Demo → Proposal]
  E -->|No x3| D
  F --> G{Win?}
  G -->|Có| H[Onboarding CSKH]
  G -->|Không| I[Long-term nurture]
```

| Trigger | Hành động auto |
|---|---|
| Form submit | CRM tag + email D0 + notify SDR |
| MQL ≥60 | Task gọi priority High |
| No answer ×3 | Chuyển nurture, pause telesales |
| Demo done | Tạo opportunity + proposal template |
| Win | Handoff CS + NPS schedule D30 |

### F. KPI chuyển tiếp (benchmark B2B)

| Chỉ số | Mục tiêu | Cảnh báo |
|---|---|---|
| MQL → SQL | ≥25% | <15% — review scoring |
| SQL → Win | ≥20% | <10% — review script/demo |
| Cycle length | ≤45 ngày | >60 — audit bottleneck |
| CAC payback | ≤12 tháng | >18 — review kênh |

**Bước tiếp theo:** **Bước 5** (script telesales) · **Bước 3** (Excel) gắn KPI tuần.
"""

# ---------------------------------------------------------------------------
# Bước 5 — Telesales
# ---------------------------------------------------------------------------
TELESALES_TEMPLATE = """**BƯỚC 5 — Script telesales & tư vấn (triển khai chi tiết)**

### A. Mục tiêu bước này
- Chuẩn hóa **cuộc gọi 8–12 phút** từ mở đầu → chốt demo.
- Xử lý **≥5 phản đối** thường gặp với talk track thống nhất.
- **100% log CRM** trong 15 phút sau cuộc gọi.

### B. Cấu trúc cuộc gọi (timeline)

| Phút | Giai đoạn | Mục tiêu |
|---|---|---|
| 0–0:15 | Mở đầu + xin phép | Giữ người nghe |
| 0:15–3:00 | SPIN khám phá | Hiểu pain & urgency |
| 3:00–4:00 | Pitch 60s | USP PTT rõ ràng |
| 4:00–7:00 | Xử lý phản đối | Không tranh cãi |
| 7:00–8:00 | Chốt bước tiếp | Lịch demo cụ thể |
| Sau gọi | CRM log | Outcome + next step |

### C. Script chi tiết

**Mở đầu:** "Xin chào anh/chị [Tên], em [Tên] từ **PTT Advertising Solutions** — bên giải pháp marketing tích hợp. Em thấy anh/chị quan tâm [dịch vụ]. Anh/chị có 2–3 phút em hỏi nhanh nhu cầu ạ?"

**SPIN:**
- **S:** "Hiện team đang chạy kênh nào — Google, Meta hay đa kênh?"
- **P:** "Điểm vướng nhất: CPL cao, lead kém chất lượng hay thiếu báo cáo?"
- **I:** "Nếu kéo dài thêm 1 quý, ảnh hưởng pipeline thế nào?"
- **N:** "Nếu giảm CPL 20–30% với tracking rõ, giá trị với team ra sao?"

**Pitch 60s:** "PTT làm 3 lớp: **chiến lược funnel+KPI** → **creative & landing** → **đo tuần**. Thường audit + pilot 4 tuần trước scale."

### D. Ma trận phản đối (mở rộng)

| Phản đối | Phản hồi | Bước tiếp |
|---|---|---|
| "Gửi báo giá email" | "Em gửi được, nhưng để sát ngành cần 20' demo — em chuẩn bị 1 trang đề xuất riêng." | Chốt lịch |
| "Có agency rồi" | "PTT hay audit/pilot 1 mảng (tracking/creative) song song." | Offer audit |
| "Chưa có ngân sách" | "Mình lên kế hoạch Q+1 + template Excel tuần." | Gửi Excel |
| "Bận, gọi lại" | "Thứ [X] [giờ] em gọi lại 5 phút được không?" | Task CRM |
| "So sánh giá" | "Em so sánh theo **CPL/SQL và scope** — em gửi bảng so sánh sau demo." | Demo |
| "Cần hỏi sếp" | "Em gửi slide 1 trang + book luôn slot sếp tham gia 15' cuối demo." | Multi-stakeholder |

### E. Chốt lịch & follow-up
"Anh/chị **thứ [ngày] [giờ]** hay **[ngày 2] [giờ 2]** tiện demo 30 phút? Em gửi invite ngay."

**Follow-up nếu không bắt máy:** SMS/Zalo D0 · Email case D+1 · Gọi lại D+2 (tối đa 3 lần/tuần).

### F. Checklist CRM (bắt buộc ≤15 phút)
- [ ] Outcome: Connected / Voicemail / Wrong number / Not interested
- [ ] Objection tag (giá / timing / đối thủ / no budget)
- [ ] Pain chính (1 dòng)
- [ ] Next step + deadline
- [ ] Attach proposal / calendar invite nếu có

```chart-json
{"type":"bar","title":"Contact rate theo SDR (minh họa)","labels":["SDR A","SDR B","SDR C"],"values":[68,72,55]}
```

**Bước tiếp theo:** Gắn SLA vào **Bước 4** funnel · Log KPI trên **Bước 3** Excel.
"""

# ---------------------------------------------------------------------------
# Bước 6 — Đa kênh
# ---------------------------------------------------------------------------
MULTICHANNEL_PLAN_TEMPLATE = """**BƯỚC 6 — Kế hoạch truyền thông đa kênh (triển khai chi tiết)**

### A. Mục tiêu bước này
- Lập **KH 3 tháng** đồng bộ Paid / Owned / Earned theo funnel.
- Mỗi kênh có: vai trò · message · format · budget · KPI · owner.
- Lịch phát sinh asset + báo cáo cross-channel hàng tuần.

### B. Khung lập kế hoạch (7 bước con)
1. **SMART goal** — ví dụ: +40% MQL chất lượng, SQL rate ≥25%, CPL ≤220k.
2. **Insight & ICP** — pain, kênh tin cậy, hành vi mua.
3. **Big Idea + key message** — 1 idea, message khác nhau theo funnel.
4. **Channel mix** — ma trận P/O/E, không phụ thuộc >70% 1 kênh.
5. **Lịch phát sinh** — tuần × kênh × asset × deadline duyệt.
6. **Ngân sách & pacing** — base/test/reserve 10%.
7. **Measurement** — UTM, CRM tag, dashboard tuần.

### C. Ma trận kênh chi tiết

| Kênh | P/O/E | Funnel | Message | Format | NS/tháng | KPI | Owner |
|---|---|---|---|---|---|---|---|
| Google Search | Paid | Conversion | Audit funnel free | RSA+ext | 45M | CPL≤250k | Ads |
| Meta | Paid | Consideration | Case + proof | Carousel/Video | 36M | CPL≤180k | Social |
| TikTok | Paid | Awareness | Hook pain CPL | 15s video | 15M | CPV | Social |
| LinkedIn | Paid | B2B Lead | Whitepaper | Lead form | 20M | CPL≤350k | Ads |
| Landing | Owned | Conversion | USP + form | A/B page | 8M | CVR≥4% | CRO |
| Email | Owned | Nurture | D0-D14 seq | Automation | 3M | Open≥25% | CRM |
| SEO | Owned | Consideration | Pillar AEO | 4 bài/th | 12M | Organic lead | Content |
| KOL/PR | Earned | Awareness | Review | Video 60s | 10M | Referral CPL | PR |

### D. Lịch phát sinh tháng 1 (mẫu)

| Tuần | Kênh | Asset | Deadline | Owner | Status |
|---|---|---|---|---|---|
| W1 | Google+Meta | Launch Q2 | T2 | Ads Lead | Duyệt |
| W1 | Email | Nurture v1 | T4 | CRM | Soạn |
| W2 | TikTok | 3 hook test | T3 | Social | Quay |
| W3 | Landing | A/B form | T5 | CRO | Dev |
| W4 | All | Báo cáo cross-channel | T6 | MKT Lead | Review |

### E. Đồng bộ đo lường
- **UTM naming:** `source_medium_campaign_content`
- **CRM:** tag nguồn = utm_source + campaign
- **Báo cáo T6:** spend · CPL · MQL · SQL by channel · learnings

```chart-json
{"type":"pie","title":"Phân bổ ngân sách đa kênh","labels":["Google","Meta","LinkedIn","TikTok","Content","Email","KOL","CRO"],"values":[30,24,13,10,8,3,7,5]}
```

```mermaid
flowchart LR
  A[Awareness TikTok/PR] --> B[Consider Meta/SEO]
  B --> C[Convert Google/Landing]
  C --> D[Nurture Email]
  D --> E[Sales SQL]
```

### F. Checklist hoàn thành
- [ ] Tải Excel — nút **ĐK** (4 sheet: kênh, lịch, test, hướng dẫn)
- [ ] 100% kênh có owner + KPI
- [ ] UTM doc share team
- [ ] Lịch họp cross-channel T6

**Bước tiếp theo:** **Bước 7** test từng kênh trước khi scale budget.
"""

# ---------------------------------------------------------------------------
# Bước 7 — Test kênh
# ---------------------------------------------------------------------------
CHANNEL_TEST_TEMPLATE = """**BƯỚC 7 — Phương pháp test kênh có kiểm soát (triển khai chi tiết)**

### A. Mục tiêu bước này
- **Không scale** trên cảm tính — mọi quyết định dựa trên giả thuyết đăng ký trước.
- 1 test = 1 biến số chính + đủ mẫu + ngưỡng Scale/Iterate/Kill.
- Log vào sheet **Test_matrix** (Excel **ĐK**).

### B. Khung 6 bước test
1. **Register H:** "Nếu [X] thì [metric Y] cải thiện ≥Z%."
2. **Design:** 2–3 variant, budget chia đều, thời gian cố định.
3. **QA tracking:** pixel/CAPI/UTM/CRM trước khi bật.
4. **Run:** không dừng sớm trước min sample.
5. **Analyze:** primary metric + lead quality (SQL rate).
6. **Decide:** Scale 20–30% / Iterate / Kill + ghi bài học.

### C. Ma trận test theo kênh (chi tiết)

| Kênh | Test | Thời gian | Min sample | Primary | Ngưỡng thắng | Secondary |
|---|---|---|---|---|---|---|
| Google Search | RSA headline ×3 | 14 ngày | ≥300 click/var | CPL | ↓15% vs control | CTR, CVR |
| Google Search | Landing A/B | 21 ngày | ≥200 click | CVR | ↑10% | CPL |
| Meta | Static vs Video | 7–14 ngày | ≥50 conv/set | CPL | ↓12% | Freq, CTR |
| Meta | Broad vs Interest | 14 ngày | ≥30 conv | SQL rate | Cao hơn control | CPL |
| TikTok | Hook 3s A/B/C | 5–7 ngày | ≥50k views | CTR out | Cao nhất | CPV |
| Email | Subject A/B | 1 send | ≥1000/branch | Open | ↑10% | Click, CVR |
| SEO | Title/meta GSC | 4–6 tuần | ≥100 imp | CTR | +1–2 điểm % | Position |
| KOL | 2 KOL same brief | 14 ngày | 1 vid/KOL | Ref CPL | Thấp hơn + quality | Reach |

### D. Template đăng ký test (copy vào sheet)

| Trường | Nội dung mẫu |
|---|---|
| Giả thuyết | Headline pain hook giảm CPL ≥15% |
| Biến số | RSA headline only |
| Control | "Dịch vụ quảng cáo Google" |
| Variant | "Giảm CPL — Audit miễn phí" |
| Thời gian | 14 ngày (không dừng sớm) |
| Min sample | 300 click/variant |
| Primary | CPL |
| Ngưỡng thắng | CPL variant ≤ control × 0.85 |
| Quyết định nếu thua | Iterate hook landing (Bước 4) |

### E. Quy trình quyết định

```mermaid
flowchart TD
  R[Register H + metric] --> Q[QA tracking]
  Q --> Run[Run đủ mẫu]
  Run --> M{Đạt ngưỡng 2 tuần liên tiếp?}
  M -->|Có| S[Scale budget 20-30%]
  M -->|Gần đạt| I[Iterate 1 biến số]
  M -->|Fail| K[Kill + post-mortem]
  S --> L[Log learnings]
  I --> L
  K --> L
```

### F. Checklist trước scale
- [ ] Tracking 100% OK
- [ ] UTM + CRM tag verified
- [ ] Primary metric đạt ngưỡng ≥2 chu kỳ tuần
- [ ] SQL rate không giảm khi tăng budget
- [ ] Post-mortem ghi vào Test_matrix

```chart-json
{"type":"bar","title":"CPL variant vs control","labels":["Control","Variant A","Variant B"],"values":[280,235,248]}
```

**Bước tiếp theo:** Scale winner → cập nhật **Bước 3** Excel · điều chỉnh **Bước 6** budget mix.
"""

STEP_TEMPLATES: dict[str, str] = {
    step_id: append_practice(base, step_id)
    for step_id, base in {
        "ads_copy": ADS_TEMPLATE,
        "tvc_kol": TVC_KOL_TEMPLATE,
        "excel_weekly": EXCEL_WEEKLY_TEMPLATE,
        "funnel": FUNNEL_TEMPLATE,
        "telesales": TELESALES_TEMPLATE,
        "multichannel_plan": MULTICHANNEL_PLAN_TEMPLATE,
        "channel_test": CHANNEL_TEST_TEMPLATE,
    }.items()
}

STEP_NUMBER_MAP: dict[str, str] = {
    "1": "ads_copy",
    "2": "tvc_kol",
    "3": "excel_weekly",
    "4": "funnel",
    "5": "telesales",
    "6": "multichannel_plan",
    "7": "channel_test",
}
