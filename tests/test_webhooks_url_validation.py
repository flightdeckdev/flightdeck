"""SSRF-defence tests for ``WebhookCreate.url`` validation.

The validator must reject:
- schemes other than http / https
- link-local IP literals (covers all cloud-metadata endpoints)
- known cloud-metadata hostnames

The validator must accept:
- plain HTTPS and HTTP public URLs
- private RFC1918 addresses (self-hosted Slack / Discord receivers)
- loopback (local dev / webhook.site-style local relays)

Rationale lives in the validator docstring in
``src/flightdeck/models.py``. The threat model is an operator with
ledger-write access who could otherwise register a URL that exfiltrates
promote / rollback payloads to a cloud metadata endpoint or an internal
service of their choosing.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flightdeck.models import WebhookCreate


def _make(url: str) -> WebhookCreate:
    return WebhookCreate(url=url, events=["promote.succeeded"])


@pytest.mark.parametrize(
    "url",
    [
        "https://hooks.slack.com/services/T000/B000/abc",
        "https://example.com/webhook",
        "http://localhost:8080/relay",
        "http://127.0.0.1:5000/dev",
        "http://10.0.0.5/internal-slack",
        "http://192.168.1.10/receiver",
        "http://172.16.0.7:9000/hook",
    ],
)
def test_valid_urls_accepted(url: str) -> None:
    """Public, loopback, and RFC1918 private addresses are all allowed."""
    wh = _make(url)
    assert wh.url == url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://attacker.example/",
        "ftp://attacker.example/",
        "javascript:alert(1)",
        "data:text/plain,hello",
    ],
)
def test_disallowed_schemes_rejected(url: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make(url)
    assert "scheme" in str(exc_info.value).lower()


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # AWS IMDS
        "http://169.254.170.2/v2/credentials/",  # ECS task role
        "http://[fe80::1]/",  # IPv6 link-local
        "http://[fe80::abcd:1234]/path",
    ],
)
def test_link_local_addresses_rejected(url: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make(url)
    msg = str(exc_info.value).lower()
    assert "link-local" in msg or "metadata" in msg


@pytest.mark.parametrize(
    "url",
    [
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://metadata/",
        "http://instance-data/",
        "http://instance-data.ec2.internal/",
    ],
)
def test_metadata_hostnames_rejected(url: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make(url)
    assert "metadata" in str(exc_info.value).lower()


def test_empty_host_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make("https:///no-host")
    assert "host" in str(exc_info.value).lower()
