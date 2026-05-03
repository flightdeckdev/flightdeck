"""Optional OpenTelemetry wiring (``telemetry`` extra)."""

from __future__ import annotations

import os

import pytest


def test_configure_otel_tracing_import_and_idempotent() -> None:
    pytest.importorskip("opentelemetry.sdk")
    pytest.importorskip("opentelemetry.exporter.otlp.proto.http.trace_exporter")

    from opentelemetry import trace

    from flightdeck.integrations import telemetry as tel

    prev = trace.get_tracer_provider()
    os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:9/v1/traces")
    try:
        assert tel.configure_otel_tracing(force=True) is True
        assert tel.configure_otel_tracing() is False
    finally:
        trace.set_tracer_provider(prev)
        tel._configured = False  # type: ignore[attr-defined]
