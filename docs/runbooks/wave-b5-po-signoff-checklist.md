# Wave B5 — PO sign-off checklist (production)

> Dùng sau `./scripts/wave_b5_deploy.sh` + gate PASS trên VPS.  
> Tham chiếu UAT: [`huong-dan-day-du-lead-den-cham-soc-khach-hang.md`](../crm/huong-dan-day-du-lead-den-cham-soc-khach-hang.md) §9–13

**Env prod bắt buộc:**

```bash
PTT_CRM_SERVICE_DELIVERY_NEST=1
PTT_CRM_LEADS_FUNNEL_NEST=1
PTT_PRESALES_ON_LEAD=1
PTT_SOP_AUTO_START_ON_LAUNCH=1   # nếu FR-SD-02 trong release
```

**Automated gates:**

```bash
cd /var/www/ptt
WAVE_B5_UPDATE_ENV=1 ./scripts/wave_b5_deploy.sh
./scripts/wave_b5_gate.sh
./scripts/wave_b5_pytest_parity.sh
ADMIN_PASSWORD='...' ./scripts/wave_b5_s0_smoke.sh
```

---

## Checklist PO

| # | Tiêu chí | Pass? | Ghi chú |
|---|----------|-------|---------|
| 1 | B4 signed — presales 3 tab + KH MKT sơ bộ trên prod | ☐ | |
| 2 | AM submit HĐ → GDKD approve → lifecycle **Onboard** (không Flask) | ☐ | `/crm/leads/[id]` + `/crm/hub` |
| 3 | Kanban 7 cột `/crm/service-delivery` | ☐ | |
| 4 | Workflow detail — tick tasks, progress bar | ☐ | `/crm/service-delivery/[id]` |
| 5 | Advance tuần tự — block khi task chưa ✓ | ☐ | |
| 6 | Gate TMMT block Onboard→Deliver khi chưa đủ | ☐ | |
| 7 | Chi phí pre-sales hiển thị sau promote | ☐ | Finance panel |
| 8 | SOP run auto sau GDKD approve (nếu bật flag) | ☐ | `/crm/sop/runs` |
| 9 | `wave_b5_gate.sh` + pytest parity PASS | ☐ | |
| 10 | Manual UAT §9–13 signed | ☐ | |

**PO ký:** ___________________ **Ngày:** ___________

**Tech lead:** ___________________ **Ngày:** ___________
