"""Типизированные курсоры инкрементальности.

Каждый курсор (де)сериализуется в state-dict (jsonb-совместимый). Адаптер объявляет
cursor_kind и работает со своим курсором через from_state/to_state, а оркестратор
понимает семантику курсора декларативно.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.adapters.base import State

_SEEN_LIMIT = 5000


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


class ETagCursor(BaseModel):
    """RSS/HTTP: ETag для условного запроса + окно виденных guid."""

    etag: str | None = None
    seen_guids: list[str] = Field(default_factory=list)

    @classmethod
    def from_state(cls, state: State) -> "ETagCursor":
        return cls(
            etag=state.get("etag"),
            seen_guids=list(state.get("seen_guids", [])),
        )

    def to_state(self) -> State:
        return {
            "etag": self.etag,
            "seen_guids": self.seen_guids[-_SEEN_LIMIT:],
        }

    def remember(self, guid: str) -> None:
        self.seen_guids.append(guid)

    def has_seen(self, guid: str) -> bool:
        return guid in set(self.seen_guids)


class TimestampCursor(BaseModel):
    """Sitemap/API: верхняя граница уже обработанных публикаций."""

    last_published_at: datetime | None = None

    @classmethod
    def from_state(cls, state: State) -> "TimestampCursor":
        return cls(last_published_at=_parse_dt(state.get("last_published_at")))

    def to_state(self) -> State:
        return {
            "last_published_at": (
                self.last_published_at.isoformat() if self.last_published_at is not None else None
            ),
        }


class SinceIdCursor(BaseModel):
    """Соцсети фазы 2: монотонный id последнего обработанного поста."""

    since_id: str | None = None

    @classmethod
    def from_state(cls, state: State) -> "SinceIdCursor":
        return cls(since_id=state.get("since_id"))

    def to_state(self) -> State:
        return {"since_id": self.since_id}


class PageCursor(BaseModel):
    """Пагинируемые API: номер страницы/оффсет."""

    page: int = 0
    offset: int = 0

    @classmethod
    def from_state(cls, state: State) -> "PageCursor":
        return cls(page=int(state.get("page", 0)), offset=int(state.get("offset", 0)))

    def to_state(self) -> State:
        return {"page": self.page, "offset": self.offset}
