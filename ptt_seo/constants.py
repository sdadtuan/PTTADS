"""SEO/AEO service slugs and workflow constants."""
from __future__ import annotations

SEO_AEO_SERVICE_SLUGS: frozenset[str] = frozenset(
    {
        "dich-vu-aeo",
        "dich-vu-seo-tong-the",
        "dich-vu-seo-local",
        "dich-vu-seo-audit",
    }
)

SEO_SERVICE_SLUGS: frozenset[str] = frozenset(
    {
        "dich-vu-seo-tong-the",
        "dich-vu-seo-local",
        "dich-vu-seo-audit",
    }
)

INITIATIVE_ROADMAP_BUCKETS: tuple[str, ...] = ("30d", "60d", "90d")
INITIATIVE_STATUSES: tuple[str, ...] = ("planned", "in_progress", "done", "cancelled")
IMPACT_LEVELS: tuple[str, ...] = ("low", "medium", "high")

INTENTS: tuple[str, ...] = ("informational", "commercial", "transactional", "navigational")
CONTENT_TYPES: tuple[str, ...] = (
    "blog",
    "pillar",
    "service",
    "landing",
    "faq",
    "comparison",
    "howto",
    "glossary",
    "local",
    "product",
)

CONTENT_WORKFLOW_STATUSES: tuple[str, ...] = (
    "idea",
    "researching",
    "brief_ready",
    "in_writing",
    "seo_review",
    "aeo_review",
    "technical_review",
    "client_review",
    "approved",
    "published",
    "monitoring",
    "refresh_required",
    "archived",
)

# Kanban columns (Phase 2 UI — Gate B: separate review stages per wireframe S-07)
PIPELINE_COLUMNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("idea", ("idea", "researching")),
    ("brief_ready", ("brief_ready",)),
    ("in_writing", ("in_writing",)),
    ("seo_review", ("seo_review",)),
    ("aeo_review", ("aeo_review",)),
    ("technical_review", ("technical_review",)),
    ("client_review", ("client_review",)),
    ("approved", ("approved",)),
    ("published", ("published", "monitoring")),
    ("refresh", ("refresh_required",)),
)

CONTENT_STATUS_LABELS: dict[str, str] = {
    "idea": "Ý tưởng",
    "researching": "Research",
    "brief_ready": "Brief sẵn sàng",
    "in_writing": "Đang viết",
    "seo_review": "SEO Review",
    "aeo_review": "AEO Review",
    "technical_review": "Technical Review",
    "client_review": "Client Review",
    "approved": "Đã duyệt",
    "published": "Đã publish",
    "monitoring": "Monitoring",
    "refresh_required": "Cần refresh",
    "archived": "Lưu trữ",
}

# Allowed forward transitions (Phase 2)
CONTENT_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "idea": ("researching", "brief_ready", "archived"),
    "researching": ("brief_ready", "idea", "archived"),
    "brief_ready": ("in_writing", "researching", "archived"),
    "in_writing": ("seo_review", "brief_ready", "archived"),
    "seo_review": ("aeo_review", "in_writing", "archived"),
    "aeo_review": ("approved", "technical_review", "in_writing", "archived"),
    "technical_review": ("client_review", "approved", "in_writing", "archived"),
    "client_review": ("approved", "in_writing", "archived"),
    "approved": ("published", "in_writing", "archived"),
    "published": ("monitoring", "refresh_required", "archived"),
    "monitoring": ("refresh_required", "archived"),
    "refresh_required": ("in_writing", "researching", "archived"),
    "archived": ("idea",),
}

APPROVAL_STAGES: tuple[str, ...] = ("seo_review", "aeo_review", "technical_review", "client_review")


def is_seo_aeo_service_slug(slug: str | None) -> bool:
    return str(slug or "").strip() in SEO_AEO_SERVICE_SLUGS


def project_type_for_slug(slug: str | None) -> str:
    s = str(slug or "").strip()
    if s == "dich-vu-aeo":
        return "aeo"
    if s in SEO_SERVICE_SLUGS:
        return "seo"
    return "hybrid"


def can_transition(current: str, target: str) -> bool:
    return target in CONTENT_TRANSITIONS.get(current, ())
