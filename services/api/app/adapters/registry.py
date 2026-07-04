"""Реестр адаптеров источников.

Декоратор @AdapterRegistry.register регистрирует инстанс адаптера по его type.
describe() отдаёт config_schema + capabilities — готовое API для M4-формы источника
(UI рисует форму из JSON-схемы, секрет-поля исключены). REGISTRY — алиас с
__contains__/__getitem__ для обратной совместимости с `req.type in REGISTRY`.
"""

from typing import TypeVar

from app.adapters.base import SourceAdapter

AdapterT = TypeVar("AdapterT", bound=type)


class _AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}

    def register(self, adapter_cls: AdapterT) -> AdapterT:
        instance = adapter_cls()
        self._adapters[instance.type] = instance
        return adapter_cls

    def get(self, source_type: str) -> SourceAdapter:
        return self._adapters[source_type]

    def types(self) -> list[str]:
        return sorted(self._adapters)

    def describe(self) -> list[dict]:
        described: list[dict] = []
        for source_type in self.types():
            adapter = self._adapters[source_type]
            described.append(
                {
                    "type": source_type,
                    "capabilities": adapter.capabilities.model_dump(),
                    "config_schema": _strip_secrets(adapter.config_model),
                }
            )
        return described

    def __contains__(self, source_type: object) -> bool:
        return source_type in self._adapters

    def __getitem__(self, source_type: str) -> SourceAdapter:
        return self._adapters[source_type]

    def __iter__(self):
        return iter(self._adapters)

    def __len__(self) -> int:
        return len(self._adapters)


def _strip_secrets(config_model: type) -> dict:
    """JSON-схема config без секрет-полей (SecretStr или json_schema_extra secret=True)."""
    schema = config_model.model_json_schema()
    properties = schema.get("properties", {})
    secret_fields = set()
    for name, field in getattr(config_model, "model_fields", {}).items():
        extra = field.json_schema_extra
        if isinstance(extra, dict) and extra.get("secret"):
            secret_fields.add(name)
        annotation = getattr(field.annotation, "__name__", "")
        if annotation == "SecretStr":
            secret_fields.add(name)
    for name in secret_fields:
        properties.pop(name, None)
        if name in schema.get("required", []):
            schema["required"].remove(name)
    return schema


AdapterRegistry = _AdapterRegistry()
REGISTRY = AdapterRegistry
