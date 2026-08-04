"""OTel bootstrap + structured logging (Phase A: logs).

Весь модуль импортируется условно — при OTEL_ENABLED=false
OTel SDK не инициализируется, structlog работает в базовом режиме.
"""

from __future__ import annotations

import contextvars
import logging
import sys
from typing import Any

import structlog

# --- contextvars для корреляции логов ---
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
tenant_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("tenant_id", default="")
user_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")
stage_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("stage", default="")


def setup_otel(service_name: str = "kate-api") -> None:
    """Инициализация OTel SDK + лог-экспорт + авто-инструментация. Вызывать один раз при старте."""
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": service_name})

    # Traces
    tp = TracerProvider(resource=resource)
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tp)

    # Logs
    lp = LoggerProvider(resource=resource)
    lp.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    handler = LoggingHandler(level=logging.INFO, logger_provider=lp)
    logging.getLogger().addHandler(handler)

    # Авто-инструментация (zero-code)
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    FastAPIInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    CeleryInstrumentor().instrument()
    RedisInstrumentor().instrument()
    LoggingInstrumentor().instrument()


def configure_structlog(*, json_output: bool | None = None) -> None:
    """Настройка structlog: JSON в проде/dev, console в tty.

    Args:
        json_output: None = авто (JSON если не tty), True = всегда JSON, False = всегда console.
    """
    if json_output is None:
        json_output = not sys.stderr.isatty()

    try:
        from opentelemetry import trace
    except ImportError:
        trace = None  # type: ignore[assignment]

    def add_trace_info(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        if trace is not None:
            span = trace.get_current_span()
            ctx = span.get_span_context()
            if ctx and ctx.trace_id:
                event_dict["trace_id"] = format(ctx.trace_id, "032x")
                event_dict["span_id"] = format(ctx.span_id, "016x")
        event_dict["request_id"] = request_id_ctx.get("")
        event_dict["tenant_id"] = tenant_id_ctx.get("")
        event_dict["user_id"] = user_id_ctx.get("")
        event_dict["stage"] = stage_ctx.get("")
        return event_dict

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        add_trace_info,
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger() -> Any:
    """Получить structlog-логер."""
    return structlog.get_logger()
