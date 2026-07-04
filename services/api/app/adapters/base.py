"""Контракт адаптера источника.

Всё специфичное для типа источника (курсор, нужен ли JS-рендер, отдаёт ли полный
текст, лимит частоты) выносится в декларативные AdapterCapabilities и config_model.
Оркестратор ветвится по флагам capabilities, а не по строке source.type.
"""

from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.models import Document

Raw = dict[str, Any]
State = dict[str, Any]

CursorKind = Literal["etag", "timestamp", "since_id", "page", "none"]
FetchMode = Literal["incremental", "backfill", "test"]


class AdapterCapabilities(BaseModel):
    """Декларативные свойства источника, по которым ветвится оркестратор."""

    cursor_kind: CursorKind
    supports_incremental: bool = True
    supports_backfill: bool = False
    provides_full_text: bool = False
    needs_javascript: bool = False
    respects_robots: bool = True
    emits_media: bool = False
    default_rate_limit_rpm: int = 60


class FetchRequest(BaseModel):
    """Запрос на выборку сырья. mode/limit/since управляют инкрементом и тестом."""

    source: dict
    state: State = Field(default_factory=dict)
    mode: FetchMode = "incremental"
    limit: int | None = None
    since: datetime | None = None


class FetchStats(BaseModel):
    fetched: int = 0
    new: int = 0
    skipped: int = 0


class FetchResult(BaseModel):
    """Результат выборки: сырьё, новый курсор, флаг пагинации, предупреждения."""

    items: list[Raw] = Field(default_factory=list)
    state: State = Field(default_factory=dict)
    has_more: bool = False
    warnings: list[str] = Field(default_factory=list)
    stats: FetchStats = Field(default_factory=FetchStats)


@runtime_checkable
class SourceAdapter(Protocol):
    """Протокол источника. Один шов: любой источник -> Document -> articles."""

    type: str
    capabilities: AdapterCapabilities
    config_model: type[BaseModel]

    def fetch(self, request: FetchRequest) -> FetchResult:
        """Вернуть сырьё по курсору request.state и обновлённый курсор."""
        ...

    def normalize(self, source: dict, raw: Raw) -> Document:
        """Привести сырой элемент к канонической Document."""
        ...

    def validate_config(self, config: dict) -> BaseModel:
        """Провалидировать config источника через config_model."""
        ...


class BaseAdapter:
    """Общая реализация validate_config через объявленный config_model."""

    type: str
    capabilities: AdapterCapabilities
    config_model: type[BaseModel]

    def validate_config(self, config: dict) -> BaseModel:
        return self.config_model(**(config or {}))
