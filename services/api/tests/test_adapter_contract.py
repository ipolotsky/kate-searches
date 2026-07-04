"""Контракт адаптера: модели валидируются, курсоры round-trip, Protocol проверяем."""

from datetime import UTC, datetime

from pydantic import BaseModel

from app.adapters.base import (
    AdapterCapabilities,
    BaseAdapter,
    FetchRequest,
    FetchResult,
    FetchStats,
    SourceAdapter,
)
from app.adapters.cursors import ETagCursor, PageCursor, SinceIdCursor, TimestampCursor
from app.models import Document


def test_capabilities_and_request_defaults() -> None:
    caps = AdapterCapabilities(cursor_kind="etag")
    assert caps.supports_incremental is True
    assert caps.default_rate_limit_rpm == 60

    req = FetchRequest(source={"url": "https://x.test"})
    assert req.mode == "incremental"
    assert req.limit is None
    assert req.state == {}


def test_fetch_result_defaults() -> None:
    result = FetchResult(stats=FetchStats(fetched=1, new=1, skipped=0))
    assert result.has_more is False
    assert result.warnings == []
    assert result.items == []


def test_etag_cursor_round_trip() -> None:
    cursor = ETagCursor(etag="abc", seen_guids=["a", "b"])
    restored = ETagCursor.from_state(cursor.to_state())
    assert restored.etag == "abc"
    assert restored.seen_guids == ["a", "b"]
    assert restored.has_seen("a") is True
    assert restored.has_seen("z") is False


def test_etag_cursor_caps_seen_window() -> None:
    cursor = ETagCursor(seen_guids=[str(i) for i in range(6000)])
    state = cursor.to_state()
    assert len(state["seen_guids"]) == 5000
    assert state["seen_guids"][-1] == "5999"


def test_timestamp_cursor_round_trip() -> None:
    now = datetime(2026, 7, 3, 6, 0, tzinfo=UTC)
    cursor = TimestampCursor(last_published_at=now)
    restored = TimestampCursor.from_state(cursor.to_state())
    assert restored.last_published_at == now

    empty = TimestampCursor.from_state({})
    assert empty.last_published_at is None


def test_since_id_and_page_cursor_round_trip() -> None:
    since = SinceIdCursor(since_id="42")
    assert SinceIdCursor.from_state(since.to_state()).since_id == "42"

    page = PageCursor(page=3, offset=60)
    restored = PageCursor.from_state(page.to_state())
    assert (restored.page, restored.offset) == (3, 60)


class _FakeConfig(BaseModel):
    pass


class _FakeAdapter(BaseAdapter):
    type = "fake"
    capabilities = AdapterCapabilities(cursor_kind="none")
    config_model = _FakeConfig

    def fetch(self, request: FetchRequest) -> FetchResult:
        return FetchResult(stats=FetchStats())

    def normalize(self, source: dict, raw: dict) -> Document:
        raise NotImplementedError


def test_stub_satisfies_protocol() -> None:
    assert isinstance(_FakeAdapter(), SourceAdapter)


def test_document_allows_dateless_and_body_flag() -> None:
    doc = Document(
        id="x",
        tenant_id="t",
        source_id="s",
        source_type="rss",
        url="https://x.test/a",
        canonical_url="https://x.test/a",
        title="t",
        body="b",
        fetched_at=datetime.now(UTC),
        content_hash="h",
    )
    assert doc.published_at is None
    assert doc.body_is_complete is False
