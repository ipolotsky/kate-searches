"""Кластерный канон дедупа: единственный winner по priority/recency, независимо от порядка."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.worker.tasks import _pick_canonical


@dataclass
class _StubArticle:
    id: uuid.UUID
    source_id: uuid.UUID
    published_at: datetime
    simhash: int | None = None


def _article(source_id, published) -> _StubArticle:
    return _StubArticle(id=uuid.uuid4(), source_id=source_id, published_at=published)


def test_highest_priority_wins_regardless_of_order() -> None:
    s_low, s_high, s_mid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    priority = {s_low: 3, s_high: 5, s_mid: 4}
    now = datetime(2026, 7, 4, 10, tzinfo=UTC)
    a = _article(s_low, now)
    b = _article(s_high, now)
    c = _article(s_mid, now)
    for order in ([a, b, c], [c, a, b], [b, c, a], [c, b, a]):
        assert _pick_canonical(priority, order).source_id == s_high


def test_equal_priority_earlier_published_wins() -> None:
    s1, s2 = uuid.uuid4(), uuid.uuid4()
    priority = {s1: 4, s2: 4}
    early = _article(s1, datetime(2026, 7, 4, 6, tzinfo=UTC))
    late = _article(s2, datetime(2026, 7, 4, 9, tzinfo=UTC))
    assert _pick_canonical(priority, [late, early]).id == early.id
    assert _pick_canonical(priority, [early, late]).id == early.id


def test_single_element_cluster_returns_itself() -> None:
    s = uuid.uuid4()
    only = _article(s, datetime(2026, 7, 4, tzinfo=UTC))
    assert _pick_canonical({s: 3}, [only]).id == only.id
