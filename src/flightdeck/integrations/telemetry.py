"""Opt-in OpenTelemetry tracer registration (``telemetry`` extra).

Call :func:`configure_otel_tracing` once at process startup to export spans to **your**
OTLP endpoint (not a FlightDeck-hosted backend). Standard ``OTEL_*`` and
``OTEL_EXPORTER_OTLP_*`` environment variables are honored by the underlying exporter.
"""

from __future__ import annotations

import logging
import os

_log = logging.getLogger(__name__)
_configured = False


def configure_otel_tracing(*, force: bool = False) -> bool:
    """
    Install a :class:`~opentelemetry.sdk.trace.TracerProvider` with an OTLP HTTP
    span exporter and :class:`~opentelemetry.sdk.trace.export.BatchSpanProcessor`.

    Returns ``True`` when this call installed (or reinstalled) the provider, ``False``
    if a provider was already installed and ``force`` is ``False``.

    Requires the distribution extra ``telemetry`` (``opentelemetry-sdk`` and
    ``opentelemetry-exporter-otlp``).
    """
    global _configured
    if _configured and not force:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:  # pragma: no cover - exercised when extra missing
        raise ImportError(
            "flightdeck.integrations.telemetry requires the 'telemetry' extra "
            "(for example: uv sync --extra telemetry or pip install 'flightdeck-ai[telemetry]')."
        ) from exc

    service_name = os.environ.get("OTEL_SERVICE_NAME", "flightdeck-python").strip() or "flightdeck-python"
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _configured = True
    _log.debug("OpenTelemetry TracerProvider configured for OTLP HTTP export.")
    return True
