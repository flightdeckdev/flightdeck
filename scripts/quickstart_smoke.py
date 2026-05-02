#!/usr/bin/env python3
"""Compatibility wrapper; prefer ``uv run flightdeck-quickstart-verify`` or ``python -m flightdeck.quickstart_smoke``."""

from __future__ import annotations

from flightdeck.quickstart_smoke import quickstart_verify_main


if __name__ == "__main__":
    quickstart_verify_main()
