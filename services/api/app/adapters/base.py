"""Контракт адаптера источника.

fetch(state) инкрементально тянет сырьё по курсору и возвращает (raw_items, new_state).
normalize(raw) приводит сырьё к канонической Document.
"""

from typing import Any, Protocol, runtime_checkable

from app.models import Document

# Сырой элемент источника (форма зависит от типа источника)
Raw = dict[str, Any]
State = dict[str, Any]


@runtime_checkable
class SourceAdapter(Protocol):
    type: str

    def fetch(self, source: dict, state: State) -> tuple[list[Raw], State]:
        """Вернуть новые сырые элементы и обновлённый курсор state."""
        ...

    def normalize(self, source: dict, raw: Raw) -> Document:
        """Привести сырой элемент к Document."""
        ...
