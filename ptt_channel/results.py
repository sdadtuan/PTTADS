"""Sync / webhook result types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class SyncError:
    code: str
    message: str
    external_id: str | None = None
    retriable: bool = True


@dataclass
class SyncStats:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0


@dataclass
class SyncResult(Generic[T]):
    items: list[T] = field(default_factory=list)
    cursor: str | None = None
    has_more: bool = False
    stats: SyncStats = field(default_factory=SyncStats)
    errors: list[SyncError] = field(default_factory=list)


@dataclass
class WebhookParseResult:
    verified: bool
    events: list[Any] = field(default_factory=list)
    leads: list[Any] = field(default_factory=list)
    challenge_response: str | int | None = None
    reject_reason: str | None = None


@dataclass
class CredentialValidationResult:
    valid: bool
    expires_at: str | None = None
    scopes: list[str] = field(default_factory=list)
    message: str | None = None


@dataclass
class HealthCheckResult:
    ok: bool
    latency_ms: int | None = None
    message: str | None = None
